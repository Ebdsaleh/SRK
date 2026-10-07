"""Generic Saturn/SAROO memory-capture artifacts and safe persistence.

This module deliberately contains no title-specific addresses, signatures, or
transport protocol. A future SAROO transport can supply captured bytes here;
the capture layer records exactly what was requested, hashes every region, and
publishes the resulting artifact atomically beneath an external workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Iterable


CAPTURE_SCHEMA = "srk.saturn.saroo.capture"
CAPTURE_SCHEMA_VERSION = 1
_ADDRESS_SPACE_SIZE = 1 << 32
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class CaptureError(RuntimeError):
    """Base error for capture artifact creation or validation."""


class CaptureIntegrityError(CaptureError):
    """Raised when a persisted capture no longer matches its manifest."""


@dataclass(frozen=True)
class MemoryRange:
    """One 32-bit Saturn address range requested from a capture transport."""

    start_address: int
    size: int
    label: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.start_address, bool) or not isinstance(self.start_address, int):
            raise TypeError("capture start_address must be an integer")
        if isinstance(self.size, bool) or not isinstance(self.size, int):
            raise TypeError("capture size must be an integer")
        if self.start_address < 0 or self.start_address >= _ADDRESS_SPACE_SIZE:
            raise ValueError("capture start_address must fit in the 32-bit Saturn address space")
        if self.size <= 0:
            raise ValueError("capture size must be positive")
        if self.start_address + self.size > _ADDRESS_SPACE_SIZE:
            raise ValueError("capture range extends past the 32-bit Saturn address space")
        object.__setattr__(self, "label", str(self.label or "").strip())

    @property
    def end_address_exclusive(self) -> int:
        return self.start_address + self.size

    def contains(self, address: int) -> bool:
        return self.start_address <= int(address) < self.end_address_exclusive

    def to_descriptor(self) -> dict[str, object]:
        return {
            "label": self.label,
            "start_address": self.start_address,
            "end_address_exclusive": self.end_address_exclusive,
            "size": self.size,
        }


@dataclass(frozen=True)
class CapturedRegion:
    """Immutable captured bytes paired with the exact requested memory range."""

    memory_range: MemoryRange
    data: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.memory_range, MemoryRange):
            raise TypeError("captured region requires a MemoryRange")
        payload = bytes(self.data)
        if len(payload) != self.memory_range.size:
            raise ValueError(
                "captured byte count does not match the requested memory range "
                f"({len(payload)} != {self.memory_range.size})"
            )
        object.__setattr__(self, "data", payload)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True)
class CaptureArtifact:
    """Published capture directory and its immutable region file locations."""

    directory: Path
    manifest_path: Path
    region_paths: tuple[Path, ...]


@dataclass(frozen=True)
class CaptureVerification:
    """Integrity result for one persisted capture artifact."""

    valid: bool
    errors: tuple[str, ...] = ()

    def require_valid(self) -> None:
        if not self.valid:
            raise CaptureIntegrityError("; ".join(self.errors) or "capture is invalid")


def _utc_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, datetime):
        raise TypeError("captured_at must be a datetime or None")
    if value.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug(value: object, *, fallback: str) -> str:
    text = str(value or "").strip()
    text = _SAFE_NAME_RE.sub("_", text).strip("._-")
    return text or fallback


def _unique_directory(root: Path, stem: str) -> Path:
    candidate = root / stem
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        candidate = root / f"{stem}_{index:02d}"
        if not candidate.exists():
            return candidate
        index += 1


def _manifest_region(index: int, region: CapturedRegion, filename: str) -> dict[str, object]:
    descriptor = region.memory_range.to_descriptor()
    descriptor.update(
        {
            "index": index,
            "filename": filename,
            "sha256": region.sha256,
        }
    )
    return descriptor


class CaptureStore:
    """Persist immutable capture artifacts beneath one caller-owned workspace."""

    def __init__(self, root: os.PathLike[str] | str):
        raw = os.fspath(root).strip()
        if not raw:
            raise ValueError("capture root must not be empty")
        self.root = Path(os.path.abspath(os.path.expanduser(raw)))

    def save(
        self,
        checkpoint: str,
        regions: Iterable[CapturedRegion],
        *,
        captured_at: datetime | None = None,
        session_label: str = "",
    ) -> CaptureArtifact:
        """Atomically publish one capture directory and JSON manifest.

        Region files are fully written in a temporary sibling directory first.
        Only after every payload and the manifest succeed is the directory moved
        into its final visible name. Existing captures are never overwritten;
        collisions receive a deterministic numeric suffix.
        """

        checkpoint_text = str(checkpoint or "").strip()
        if not checkpoint_text:
            raise ValueError("capture checkpoint must not be empty")
        captured_regions = tuple(regions)
        if not captured_regions:
            raise ValueError("capture must contain at least one region")
        if any(not isinstance(region, CapturedRegion) for region in captured_regions):
            raise TypeError("capture regions must be CapturedRegion instances")

        timestamp = _utc_timestamp(captured_at)
        stamp = timestamp.strftime("%Y%m%dT%H%M%SZ")
        stem = f"{stamp}_{_slug(checkpoint_text, fallback='checkpoint')}"

        self.root.mkdir(parents=True, exist_ok=True)
        destination = _unique_directory(self.root, stem)
        staging = Path(tempfile.mkdtemp(prefix=".srk-capture-", dir=self.root))
        region_paths: list[Path] = []
        manifest_regions: list[dict[str, object]] = []

        try:
            for index, region in enumerate(captured_regions):
                memory_range = region.memory_range
                label = _slug(memory_range.label, fallback=f"region_{index:02d}")
                filename = (
                    f"{index:02d}_{label}_"
                    f"{memory_range.start_address:08X}_{memory_range.size:08X}.bin"
                )
                target = staging / filename
                with target.open("xb") as stream:
                    stream.write(region.data)
                    stream.flush()
                    os.fsync(stream.fileno())
                region_paths.append(target)
                manifest_regions.append(_manifest_region(index, region, filename))

            manifest = {
                "schema": CAPTURE_SCHEMA,
                "version": CAPTURE_SCHEMA_VERSION,
                "platform": "sega-saturn",
                "transport": "saroo",
                "checkpoint": checkpoint_text,
                "session_label": str(session_label or "").strip(),
                "captured_at_utc": _iso_utc(timestamp),
                "regions": manifest_regions,
            }
            manifest_path = staging / "capture.json"
            with manifest_path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(manifest, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            os.replace(staging, destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return CaptureArtifact(
            directory=destination,
            manifest_path=destination / "capture.json",
            region_paths=tuple(destination / path.name for path in region_paths),
        )


def load_manifest(capture_directory: os.PathLike[str] | str) -> dict[str, object]:
    directory = Path(capture_directory)
    manifest_path = directory / "capture.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureIntegrityError(f"could not read capture manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise CaptureIntegrityError("capture manifest root must be an object")
    if data.get("schema") != CAPTURE_SCHEMA:
        raise CaptureIntegrityError("capture manifest schema is not recognized")
    if data.get("version") != CAPTURE_SCHEMA_VERSION:
        raise CaptureIntegrityError("capture manifest version is not supported")
    if not isinstance(data.get("regions"), list):
        raise CaptureIntegrityError("capture manifest regions must be a list")
    return data


def verify_capture(capture_directory: os.PathLike[str] | str) -> CaptureVerification:
    """Verify every persisted region against manifest size and SHA-256."""

    directory = Path(capture_directory)
    try:
        manifest = load_manifest(directory)
    except CaptureIntegrityError as exc:
        return CaptureVerification(False, (str(exc),))

    errors: list[str] = []
    regions = manifest.get("regions", [])
    for index, descriptor in enumerate(regions):
        if not isinstance(descriptor, dict):
            errors.append(f"region {index}: descriptor is not an object")
            continue
        filename = descriptor.get("filename")
        if not isinstance(filename, str) or not filename or Path(filename).name != filename:
            errors.append(f"region {index}: unsafe or missing filename")
            continue
        path = directory / filename
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"region {index}: cannot read {filename}: {exc}")
            continue
        expected_size = descriptor.get("size")
        if not isinstance(expected_size, int) or isinstance(expected_size, bool):
            errors.append(f"region {index}: invalid size metadata")
        elif len(data) != expected_size:
            errors.append(
                f"region {index}: size mismatch for {filename} "
                f"({len(data)} != {expected_size})"
            )
        expected_hash = descriptor.get("sha256")
        actual_hash = hashlib.sha256(data).hexdigest()
        if not isinstance(expected_hash, str) or actual_hash != expected_hash:
            errors.append(f"region {index}: SHA-256 mismatch for {filename}")

    return CaptureVerification(not errors, tuple(errors))
