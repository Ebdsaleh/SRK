"""Read-only discovery of local Saturn CD/filesystem runtime evidence.

Stage 6B must not guess Sega CD block commands or filesystem APIs. This module
therefore inspects the caller's already-installed Saturn development tree and
reports concrete local evidence: GFS/CDC libraries, likely headers, textual
uses of ``GFS_*`` symbols, exact header-side API contract lines, local build/link
evidence, and SHA-256 fingerprints for the preferred installed SBL artifacts.

No file is created, modified, copied, linked, or executed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
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
class SaturnCdRuntimeArtifactFingerprint:
    role: str
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class SaturnCdRuntimeProbeReport:
    root: Path
    libraries: tuple[Path, ...]
    likely_headers: tuple[Path, ...]
    preferred_artifacts: tuple[SaturnCdRuntimeArtifactFingerprint, ...]
    api_contract_matches: tuple[SaturnCdRuntimeTextMatch, ...]
    link_matches: tuple[SaturnCdRuntimeTextMatch, ...]
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
    ".mk",
    ".cfg",
}
_BUILD_FILE_NAMES = {
    "makefile",
    "makefile.mk",
    "makefile.win",
}
_MAX_TEXT_BYTES = 1024 * 1024
_MAX_SEARCH_DEPTH = 14
_GFS_SYMBOL = re.compile(r"\bGFS_[A-Za-z0-9_]+\b", re.IGNORECASE)
_GFS_TEXT_SIGNAL = re.compile(
    r"(?:\bGFS_[A-Za-z0-9_]+\b|sega[_-]?(?:gfs|cdc)|lib(?:gfs|cdc))",
    re.IGNORECASE,
)
_LIBRARY_NAME_SIGNAL = re.compile(r"(?:gfs|cdc)", re.IGNORECASE)
_HEADER_NAME_SIGNAL = re.compile(r"(?:gfs|cdc|cd)", re.IGNORECASE)
_LINK_SIGNAL = re.compile(
    r"(?:sega[_-]?(?:gfs|cdc)|lib(?:gfs|cdc)|-l[^\s]*(?:gfs|cdc))",
    re.IGNORECASE,
)
_TARGET_API_SYMBOLS = {
    "gfs_init",
    "gfs_nameToId".casefold(),
    "gfs_open",
    "gfs_getfilesize",
    "gfs_load",
    "gfs_fread",
    "gfs_close",
    "gfs_seterrfunc",
    "gfs_geterrstat",
    "gfs_work_size",
    "gfs_dir_id",
    "gfs_dirtbl_type",
    "gfs_dirtbl_ndir",
    "gfs_dirtbl_dirid",
    "gfs_bufsiz_inf",
}
_PREFERRED_ARTIFACT_SUFFIXES = {
    "\\sbl_601\\segalib\\include\\sega_gfs.h": "gfs-header",
    "\\sbl_601\\segalib\\include\\sega_cdc.h": "cdc-header",
    "\\sbl_601\\segalib\\lib_elf\\sega_gfs.a": "gfs-library",
    "\\sbl_601\\segalib\\lib_elf\\sega_cdc.a": "cdc-library",
    "\\sbl_601\\segalib\\lib_elf\\segadgfs.a": "dgfs-library",
}


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


def _is_build_text_path(path: Path) -> bool:
    return (
        path.name.casefold() in _BUILD_FILE_NAMES
        or path.suffix.casefold() in {".mak", ".mk", ".cfg"}
    )


def _is_relevant_text_path(path: Path) -> bool:
    if path.suffix.casefold() not in _TEXT_SUFFIXES and not _is_build_text_path(path):
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
        symbols = tuple(
            sorted(
                {match.group(0) for match in _GFS_SYMBOL.finditer(raw_line)},
                key=str.casefold,
            )
        )
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _preferred_artifact_fingerprints(
    paths: Iterable[Path],
) -> tuple[SaturnCdRuntimeArtifactFingerprint, ...]:
    results: list[SaturnCdRuntimeArtifactFingerprint] = []
    for path in paths:
        folded = str(path).casefold().replace("/", "\\")
        role = None
        for suffix, candidate_role in _PREFERRED_ARTIFACT_SUFFIXES.items():
            if folded.endswith(suffix):
                role = candidate_role
                break
        if role is None:
            continue
        try:
            size = path.stat().st_size
            sha256 = _sha256_file(path)
        except OSError:
            continue
        results.append(
            SaturnCdRuntimeArtifactFingerprint(
                role=role,
                path=path,
                size=size,
                sha256=sha256,
            )
        )
    return tuple(sorted(results, key=lambda item: (item.role, str(item.path).casefold())))


def _api_contract_matches(
    matches: Iterable[SaturnCdRuntimeTextMatch],
) -> tuple[SaturnCdRuntimeTextMatch, ...]:
    selected = []
    for match in matches:
        if match.path.suffix.casefold() not in {".h", ".hpp"}:
            continue
        symbol_keys = {symbol.casefold() for symbol in match.symbols}
        if symbol_keys & _TARGET_API_SYMBOLS:
            selected.append(match)
    return tuple(selected)


def _link_matches(
    matches: Iterable[SaturnCdRuntimeTextMatch],
) -> tuple[SaturnCdRuntimeTextMatch, ...]:
    return tuple(
        match
        for match in matches
        if _is_build_text_path(match.path) and _LINK_SIGNAL.search(match.line)
    )


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

    libraries_result = _unique_sorted(libraries)
    headers_result = _unique_sorted(likely_headers)
    matches_result = tuple(
        sorted(
            text_matches,
            key=lambda item: (
                str(item.path).casefold(),
                item.line_number,
            ),
        )
    )

    return SaturnCdRuntimeProbeReport(
        root=root,
        libraries=libraries_result,
        likely_headers=headers_result,
        preferred_artifacts=_preferred_artifact_fingerprints(
            (*headers_result, *libraries_result)
        ),
        api_contract_matches=_api_contract_matches(matches_result),
        link_matches=_link_matches(matches_result),
        text_matches=matches_result,
        scanned_text_files=scanned_text_files,
        skipped_oversize_files=skipped_oversize_files,
    )
