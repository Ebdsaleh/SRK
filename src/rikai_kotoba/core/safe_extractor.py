"""Safe, generic ISO-9660 extraction for SRK.

The extractor writes only beneath a caller-provided output directory, never
modifies its logical-disc source, and refuses output paths that resolve to a
known source image, CUE sheet, or CUE track file.

Source read errors are surfaced explicitly. During tree extraction they may be
recorded and skipped so one unsupported extent (for example, an audio-track
pseudo-file) cannot silently become an empty output file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ntpath
import os
import tempfile
from typing import List, Optional, Set

from rikai_kotoba.core.disc_image import paths_refer_to_same_file
from rikai_kotoba.core.iso9660 import ISO9660PathError, ISO9660Reader


class ExtractionError(Exception):
    """Base error for generic extraction operations."""


class UnsafeExtractionPathError(ExtractionError):
    """Raised when an extraction destination is unsafe."""


@dataclass(frozen=True)
class ExtractionItemResult:
    iso_path: str
    output_path: str
    status: str
    size: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ExtractionReport:
    output_root: str
    items: List[ExtractionItemResult] = field(default_factory=list)

    @property
    def extracted_count(self) -> int:
        return sum(item.status == "extracted" for item in self.items)

    @property
    def directory_count(self) -> int:
        return sum(item.status == "directory" for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.status == "skipped_existing" for item in self.items)

    @property
    def error_count(self) -> int:
        return sum(item.status == "error" for item in self.items)


def _canonical(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def _discover_source_paths(obj: object) -> Set[str]:
    """Collect known source files from DiscImage/CueDisc-backed readers.

    The walk is intentionally capability-based so future logical sources can
    participate by exposing ``source_path``, ``cue_path``, ``files[*].path``,
    or a nested ``source`` object.
    """

    found: Set[str] = set()
    visited: Set[int] = set()

    def visit(current: object) -> None:
        if current is None:
            return
        identity = id(current)
        if identity in visited:
            return
        visited.add(identity)

        for attr in ("source_path", "cue_path"):
            value = getattr(current, attr, None)
            if value:
                found.add(_canonical(value))

        segments = getattr(current, "files", None)
        if segments:
            for segment in segments:
                value = getattr(segment, "path", None)
                if value:
                    found.add(_canonical(value))

        nested = getattr(current, "source", None)
        if nested is not None:
            visit(nested)

    visit(obj)
    return found


class ISOExtractor:
    """Safely extract files from an ``ISO9660Reader``."""

    def __init__(self, reader: ISO9660Reader) -> None:
        self.reader = reader
        self._protected_source_paths = _discover_source_paths(reader)

    def resolve_destination(
        self,
        iso_path: str,
        output_root: os.PathLike[str] | str,
    ) -> str:
        """Resolve one ISO path beneath ``output_root`` without traversal."""

        if "\x00" in iso_path:
            raise UnsafeExtractionPathError("NUL byte in ISO path")

        normalized = iso_path.replace("\\", "/").strip()
        parts = [part for part in normalized.strip("/").split("/") if part]
        if not parts:
            raise UnsafeExtractionPathError("ISO root is not a file destination")

        windows_reserved = {"CON", "PRN", "AUX", "NUL"}
        windows_reserved.update(f"COM{i}" for i in range(1, 10))
        windows_reserved.update(f"LPT{i}" for i in range(1, 10))

        for part in parts:
            if part in (".", ".."):
                raise UnsafeExtractionPathError(
                    f"Relative path component is not allowed: {part}"
                )
            native_drive, _ = os.path.splitdrive(part)
            windows_drive, _ = ntpath.splitdrive(part)
            if native_drive or windows_drive or os.path.isabs(part):
                raise UnsafeExtractionPathError(
                    f"Absolute/drive-qualified component is not allowed: {part}"
                )
            if any(char in part for char in '<>:"|?*') or part.endswith((" ", ".")):
                raise UnsafeExtractionPathError(
                    f"Non-portable output filename component: {part}"
                )
            if part.split(".", 1)[0].upper() in windows_reserved:
                raise UnsafeExtractionPathError(
                    f"Reserved output filename component: {part}"
                )

        root = os.path.abspath(os.fspath(output_root))
        target = os.path.abspath(os.path.join(root, *parts))
        root_real = os.path.realpath(root)
        target_real = os.path.realpath(target)

        try:
            common = os.path.commonpath([root_real, target_real])
        except ValueError as exc:
            raise UnsafeExtractionPathError(
                f"Extraction path escapes output root: {iso_path}"
            ) from exc

        if os.path.normcase(common) != os.path.normcase(root_real):
            raise UnsafeExtractionPathError(
                f"Extraction path escapes output root: {iso_path}"
            )

        for source in self._protected_source_paths:
            if paths_refer_to_same_file(source, target):
                raise UnsafeExtractionPathError(
                    "Refusing to overwrite a source image, CUE sheet, or track file: "
                    + target
                )

        return target

    @staticmethod
    def _write_bytes(path: str, data: bytes, *, overwrite: bool) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        if not overwrite:
            created = False
            try:
                handle = open(path, "xb")
                created = True
                with handle:
                    handle.write(data)
            except Exception:
                # Remove only a file created by this call. If "xb" failed
                # because another file already existed, that file is untouched.
                if created:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                raise
            return

        fd, temp_path = tempfile.mkstemp(
            prefix=".srk-extract-",
            suffix=".tmp",
            dir=parent or None,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise

    def extract_file(
        self,
        iso_path: str,
        output_root: os.PathLike[str] | str,
        *,
        overwrite: bool = False,
    ) -> ExtractionItemResult:
        """Extract one ISO file after a complete successful source read."""

        entry = self.reader.get_entry(iso_path)
        if entry.is_dir:
            raise ISO9660PathError(f"Cannot extract directory as file: {iso_path}")

        target = self.resolve_destination(iso_path, output_root)
        if os.path.exists(target) and not overwrite:
            raise FileExistsError(f"Output already exists: {target}")

        # Read the complete source extent before creating the destination. If a
        # logical source rejects the extent (e.g. audio track), no zero-byte or
        # partial output artifact is created.
        data = self.reader.read_file(entry)
        self._write_bytes(target, data, overwrite=overwrite)

        return ExtractionItemResult(
            iso_path=iso_path,
            output_path=target,
            status="extracted",
            size=len(data),
        )

    def extract_all(
        self,
        output_root: os.PathLike[str] | str,
        *,
        overwrite: bool = False,
        continue_on_error: bool = True,
    ) -> ExtractionReport:
        """Extract the reachable ISO tree and return a per-entry report."""

        root = os.path.abspath(os.fspath(output_root))
        report = ExtractionReport(output_root=root)

        for iso_path, entry in self.reader.walk():
            try:
                target = self.resolve_destination(iso_path, root)

                if entry.is_dir:
                    os.makedirs(target, exist_ok=True)
                    report.items.append(
                        ExtractionItemResult(
                            iso_path=iso_path,
                            output_path=target,
                            status="directory",
                        )
                    )
                    continue

                try:
                    item = self.extract_file(
                        iso_path,
                        root,
                        overwrite=overwrite,
                    )
                except FileExistsError:
                    report.items.append(
                        ExtractionItemResult(
                            iso_path=iso_path,
                            output_path=target,
                            status="skipped_existing",
                            size=entry.size,
                        )
                    )
                else:
                    report.items.append(item)

            except Exception as exc:
                if not continue_on_error:
                    raise

                # Resolve as much of the destination as is safely possible for
                # diagnostics; unsafe paths deliberately remain blank.
                try:
                    output_path = self.resolve_destination(iso_path, root)
                except Exception:
                    output_path = ""

                report.items.append(
                    ExtractionItemResult(
                        iso_path=iso_path,
                        output_path=output_path,
                        status="error",
                        size=entry.size,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )

        return report
