"""Read-only discovery of local Saturn CD/filesystem runtime evidence.

Stage 6B must not guess Sega CD block commands or filesystem APIs.  This module
therefore inspects the caller's already-installed Saturn development tree and
reports concrete local evidence: GFS/CDC libraries, likely headers, and textual
uses of ``GFS_*`` symbols in source/examples/documentation.

No file is created, modified, copied, linked, or executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Iterable


class SaturnCdRuntimeProbeError(RuntimeError):
    """Raised when local Saturn CD/filesystem evidence cannot be inspected."""


@dataclass(frozen=True)
class SaturnCdRuntimeTextMatch:
    path: Path
    line_number: int
    symbols: tuple[str, ...]
    line: str


@dataclass(frozen=True)
class SaturnCdRuntimeProbeReport:
    root: Path
    libraries: tuple[Path, ...]
    likely_headers: tuple[Path, ...]
    text_matches: tuple[SaturnCdRuntimeTextMatch, ...]
    scanned_text_files: int
    skipped_oversize_files: int


_SKIP_DIRECTORIES = {
    ".git",
    ".svn",
    "__pycache__",
    "node_modules",
}
_RELEVANT_PATH_PARTS = {
    "sbl_601",
    "segalib",
    "examples",
    "example",
    "duck",
    "saturn-docs",
    "cdc_cwx",
    "rb",
}
_TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".s",
    ".asm",
    ".txt",
    ".md",
    ".htm",
    ".html",
    ".mak",
}
_MAX_TEXT_BYTES = 1024 * 1024
_MAX_SEARCH_DEPTH = 14
_GFS_SYMBOL = re.compile(r"\bGFS_[A-Za-z0-9_]+\b", re.IGNORECASE)
_GFS_TEXT_SIGNAL = re.compile(r"(?:\bGFS_[A-Za-z0-9_]+\b|sega[_-]?gfs|libgfs)", re.IGNORECASE)
_LIBRARY_NAME_SIGNAL = re.compile(r"(?:gfs|cdc)", re.IGNORECASE)
_HEADER_NAME_SIGNAL = re.compile(r"(?:gfs|cdc|cd)", re.IGNORECASE)


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _unique_sorted(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique = {str(path).casefold(): path for path in paths}
    return tuple(sorted(unique.values(), key=lambda item: str(item).casefold()))


def _walk(root: Path):
    root_depth = len(root.parts)
    for current_text, directory_names, file_names in os.walk(root):
        current = Path(current_text)
        depth = len(current.parts) - root_depth
        directory_names[:] = sorted(
            (
                name
                for name in directory_names
                if name.casefold() not in _SKIP_DIRECTORIES
                and depth < _MAX_SEARCH_DEPTH
            ),
            key=str.casefold,
        )
        yield current, tuple(sorted(file_names, key=str.casefold))


def _is_relevant_text_path(path: Path) -> bool:
    if path.suffix.casefold() not in _TEXT_SUFFIXES:
        return False
    parts = {part.casefold() for part in path.parts}
    if parts & _RELEVANT_PATH_PARTS:
        return True
    folded_name = path.name.casefold()
    return "gfs" in folded_name or "cdc" in folded_name


def _read_text_matches(path: Path) -> tuple[SaturnCdRuntimeTextMatch, ...]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return tuple()

    matches: list[SaturnCdRuntimeTextMatch] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not _GFS_TEXT_SIGNAL.search(raw_line):
            continue
        symbols = tuple(sorted({match.group(0) for match in _GFS_SYMBOL.finditer(raw_line)}, key=str.casefold))
        compact = " ".join(raw_line.strip().split())
        if len(compact) > 220:
            compact = compact[:217] + "..."
        matches.append(
            SaturnCdRuntimeTextMatch(
                path=path,
                line_number=line_number,
                symbols=symbols,
                line=compact,
            )
        )
    return tuple(matches)


def inspect_saturn_cd_runtime_evidence(
    saturn_root: os.PathLike[str] | str,
) -> SaturnCdRuntimeProbeReport:
    """Inspect a local Saturn tree without modifying it."""

    root = _canonical(saturn_root)
    if not root.is_dir():
        raise SaturnCdRuntimeProbeError(
            f"Saturn development root is not a directory: {root}"
        )

    libraries: list[Path] = []
    likely_headers: list[Path] = []
    text_matches: list[SaturnCdRuntimeTextMatch] = []
    scanned_text_files = 0
    skipped_oversize_files = 0

    for current, file_names in _walk(root):
        for filename in file_names:
            path = (current / filename).resolve()
            suffix = path.suffix.casefold()

            if suffix in {".a", ".lib"} and _LIBRARY_NAME_SIGNAL.search(path.name):
                libraries.append(path)

            if suffix in {".h", ".hpp"} and _HEADER_NAME_SIGNAL.search(path.name):
                likely_headers.append(path)

            if not _is_relevant_text_path(path):
                continue

            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > _MAX_TEXT_BYTES:
                skipped_oversize_files += 1
                continue

            scanned_text_files += 1
            text_matches.extend(_read_text_matches(path))

    return SaturnCdRuntimeProbeReport(
        root=root,
        libraries=_unique_sorted(libraries),
        likely_headers=_unique_sorted(likely_headers),
        text_matches=tuple(
            sorted(
                text_matches,
                key=lambda item: (
                    str(item.path).casefold(),
                    item.line_number,
                ),
            )
        ),
        scanned_text_files=scanned_text_files,
        skipped_oversize_files=skipped_oversize_files,
    )
