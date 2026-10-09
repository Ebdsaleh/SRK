"""Read-only inspection of one concrete Sega Saturn standalone template.

Candidate ranking identifies directories worth reviewing.  This module performs
that review gate without copying or building anything: it fingerprints the
candidate files, decodes the local IP.BIN header when present, and returns
bounded text excerpts from build/startup/input/video sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os


class SaturnStandaloneTemplateError(RuntimeError):
    """Raised when a concrete standalone template cannot be inspected safely."""


@dataclass(frozen=True)
class SaturnStandaloneTemplateFile:
    path: Path
    relative_path: str
    size: int
    sha256: str
    role: str
    text: str | None
    truncated: bool = False


@dataclass(frozen=True)
class SaturnStandaloneTemplateReport:
    directory: Path
    files: tuple[SaturnStandaloneTemplateFile, ...]
    ip_bin: Path | None
    ip_metadata: tuple[tuple[str, str], ...]

    def file_named(self, name: str) -> SaturnStandaloneTemplateFile | None:
        wanted = str(name or "").casefold()
        for item in self.files:
            if item.path.name.casefold() == wanted:
                return item
        return None


_TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".s",
    ".asm",
    ".ld",
    ".lds",
    ".lnk",
    ".mak",
    ".mk",
    ".txt",
}
_MAKEFILE_NAMES = {"makefile", "makefile.mk", "makefile.win"}
_STARTUP_NAMES = {
    "cinit.c",
    "crt0.c",
    "crt0.s",
    "crt0.asm",
    "startup.c",
    "startup.s",
    "startup.asm",
}
_PRIORITY_SOURCE_NAMES = {
    "main.c",
    "smpc.c",
    "smpc.h",
    "conio.c",
    "conio.h",
    "video.c",
    "video.h",
    "vdp1.c",
    "vdp1.h",
    "vdp2.c",
    "vdp2.h",
}
_MAX_FILE_BYTES = 2 * 1024 * 1024
_DEFAULT_TEXT_LINES = 220
_MAX_TEXT_FILES = 32


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _role_for(path: Path) -> str:
    folded = path.name.casefold()
    suffix = path.suffix.casefold()
    if folded == "ip.bin":
        return "ip-bin"
    if folded in _MAKEFILE_NAMES or suffix == ".mak":
        return "makefile"
    if folded in _STARTUP_NAMES:
        return "startup"
    if suffix in {".ld", ".lds", ".lnk"}:
        return "linker"
    if folded in _PRIORITY_SOURCE_NAMES:
        return "priority-source"
    if suffix in {".c", ".cc", ".cpp", ".s", ".asm"}:
        return "source"
    if suffix in {".h", ".hpp"}:
        return "header"
    return "asset"


def _should_capture_text(path: Path, role: str) -> bool:
    if role in {"makefile", "startup", "linker", "priority-source"}:
        return True
    return path.suffix.casefold() in _TEXT_SUFFIXES


def _read_bounded_text(path: Path, *, max_lines: int) -> tuple[str, bool]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SaturnStandaloneTemplateError(f"cannot stat template file: {path}: {exc}") from exc
    if size > _MAX_FILE_BYTES:
        return "", True
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SaturnStandaloneTemplateError(f"cannot read template file: {path}: {exc}") from exc
    lines = text.splitlines()
    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
    return "\n".join(lines), truncated


def _decode_ascii(data: bytes) -> str:
    return data.decode("ascii", errors="replace").rstrip("\x00 ").strip()


def _parse_ip_header(path: Path) -> tuple[tuple[str, str], ...]:
    try:
        data = path.read_bytes()[:160]
    except OSError as exc:
        raise SaturnStandaloneTemplateError(f"cannot read IP.BIN: {path}: {exc}") from exc
    if len(data) < 160:
        return (("error", f"IP.BIN is too short: {len(data)} bytes"),)
    fields = (
        ("hardware_id", 0, 16),
        ("maker_id", 16, 32),
        ("device_info", 32, 48),
        ("area_symbols", 48, 56),
        ("peripherals", 56, 72),
        ("game_title", 72, 112),
        ("game_version", 112, 128),
        ("game_date", 128, 144),
        ("game_serial", 144, 160),
    )
    return tuple((name, _decode_ascii(data[start:end])) for name, start, end in fields)


def inspect_saturn_standalone_template(
    candidate_directory: os.PathLike[str] | str,
    *,
    max_text_lines: int = _DEFAULT_TEXT_LINES,
) -> SaturnStandaloneTemplateReport:
    """Inspect one candidate directory without modifying it."""

    directory = _canonical(candidate_directory)
    if not directory.is_dir():
        raise SaturnStandaloneTemplateError(
            f"standalone template candidate is not a directory: {directory}"
        )
    if max_text_lines <= 0:
        raise SaturnStandaloneTemplateError("max_text_lines must be positive")

    paths = tuple(
        sorted(
            (path.resolve() for path in directory.iterdir() if path.is_file()),
            key=lambda path: path.name.casefold(),
        )
    )
    if not paths:
        raise SaturnStandaloneTemplateError(f"standalone template candidate is empty: {directory}")

    text_candidates = [
        path for path in paths if _should_capture_text(path, _role_for(path))
    ]
    selected_text = set(text_candidates[:_MAX_TEXT_FILES])

    files: list[SaturnStandaloneTemplateFile] = []
    ip_bin: Path | None = None
    for path in paths:
        role = _role_for(path)
        text: str | None = None
        truncated = False
        if path in selected_text:
            text, truncated = _read_bounded_text(path, max_lines=max_text_lines)
        size = path.stat().st_size
        files.append(
            SaturnStandaloneTemplateFile(
                path=path,
                relative_path=path.name,
                size=size,
                sha256=_hash_file(path),
                role=role,
                text=text,
                truncated=truncated,
            )
        )
        if role == "ip-bin" and ip_bin is None:
            ip_bin = path

    return SaturnStandaloneTemplateReport(
        directory=directory,
        files=tuple(files),
        ip_bin=ip_bin,
        ip_metadata=_parse_ip_header(ip_bin) if ip_bin is not None else (),
    )
