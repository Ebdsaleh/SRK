"""Read-only ranking of locally installed Sega Saturn standalone project candidates.

The broad standalone-environment probe answers whether useful Saturn development
assets exist.  This module performs the next, still read-only, gate: identify
concrete local project directories that already contain enough boot/build
evidence to be worth reviewing before SRK generates its own standalone host.

No project is declared buildable merely because it scores highly.  The ranking
only determines which local template should be inspected first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Iterable


class SaturnStandaloneCandidateError(RuntimeError):
    """Raised when local standalone-project candidates cannot be inspected."""


@dataclass(frozen=True)
class SaturnStandaloneProjectCandidate:
    directory: Path
    makefiles: tuple[Path, ...]
    ip_bin: Path | None
    source_files: tuple[Path, ...]
    linker_files: tuple[Path, ...]
    startup_files: tuple[Path, ...]
    score: int
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class SaturnStandaloneCandidateReport:
    root: Path
    libraries: tuple[Path, ...]
    support_objects: tuple[Path, ...]
    candidates: tuple[SaturnStandaloneProjectCandidate, ...]


_SKIP_DIRECTORIES = {".git", ".svn", "__pycache__", "node_modules"}
_MAX_SEARCH_DEPTH = 10
_MAX_CANDIDATES = 20
_MAX_MAKEFILE_BYTES = 256 * 1024
_SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".s", ".asm"}
_LINKER_SUFFIXES = {".ld", ".lds", ".lnk"}
_LIBRARY_SUFFIXES = {".a", ".lib"}
_MAKEFILE_NAMES = {"makefile", "makefile.mk", "makefile.win"}
_STARTUP_NAMES = {
    "cinit.c",
    "cinit.o",
    "crt0.c",
    "crt0.o",
    "crt0.s",
    "crt0.asm",
    "startup.c",
    "startup.o",
    "startup.s",
    "startup.asm",
    "sglarea.o",
}
_SUPPORT_OBJECT_NAMES = {"cinit.o", "sglarea.o"}


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _walk(root: Path):
    root_depth = len(root.parts)
    for current_text, directory_names, file_names in os.walk(root):
        current = Path(current_text)
        depth = len(current.parts) - root_depth
        directory_names[:] = sorted(
            (
                name
                for name in directory_names
                if name not in _SKIP_DIRECTORIES and depth < _MAX_SEARCH_DEPTH
            ),
            key=str.casefold,
        )
        yield current, tuple(sorted(file_names, key=str.casefold))


def _unique_sorted(paths: Iterable[Path]) -> tuple[Path, ...]:
    unique = {str(path).casefold(): path for path in paths}
    return tuple(sorted(unique.values(), key=lambda path: str(path).casefold()))


def _is_makefile(filename: str) -> bool:
    folded = filename.casefold()
    return folded in _MAKEFILE_NAMES or folded.endswith(".mak")


def _read_makefile_signals(paths: Iterable[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        try:
            if path.stat().st_size > _MAX_MAKEFILE_BYTES:
                continue
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks).casefold()


def _path_parts(path: Path) -> set[str]:
    return {part.casefold() for part in path.parts}


def _score_candidate(
    directory: Path,
    *,
    makefiles: tuple[Path, ...],
    ip_bin: Path | None,
    sources: tuple[Path, ...],
    linker_files: tuple[Path, ...],
    startup_files: tuple[Path, ...],
) -> tuple[int, tuple[str, ...]]:
    score = 0
    evidence: list[str] = []

    if makefiles:
        score += 3
        evidence.append("makefile")
    if ip_bin is not None:
        score += 5
        evidence.append("local-ip.bin")
    if sources:
        score += 2
        evidence.append("source")
    if linker_files:
        score += 2
        evidence.append("linker-script")
    if startup_files:
        score += 2
        evidence.append("startup-object/source")

    parts = _path_parts(directory)
    if "examples" in parts or "example" in parts:
        score += 3
        evidence.append("examples-tree")
    if "sample" in parts or "samples" in parts:
        score += 2
        evidence.append("sample-tree")
    if "sgl_302j" in parts:
        score += 2
        evidence.append("sgl-tree")

    signals = _read_makefile_signals(makefiles)
    if "sh-elf" in signals:
        score += 3
        evidence.append("sh-elf-build")
    if "mkisofs" in signals or "generic-boot" in signals:
        score += 2
        evidence.append("iso-build-command")
    if "sgl_302j" in signals or "libsgl" in signals or "sglarea" in signals:
        score += 2
        evidence.append("sgl-linkage")
    if "ip.bin" in signals:
        score += 1
        evidence.append("ip.bin-reference")

    # Renesas evaluation-board samples can use the same SH compiler but are not
    # evidence of a Saturn boot environment.  Keep them visible but rank them
    # below projects carrying Saturn-specific boot/package evidence.
    lowered = str(directory).casefold().replace("/", "\\")
    if "\\sh_elf\\samples\\evb" in lowered or "\\sh_elf\\samples\\se" in lowered:
        score -= 4
        evidence.append("generic-sh-evaluation-sample")

    return score, tuple(evidence)


def inspect_saturn_standalone_candidates(
    saturn_root: os.PathLike[str] | str,
    *,
    candidate_limit: int = _MAX_CANDIDATES,
) -> SaturnStandaloneCandidateReport:
    """Rank concrete local Saturn project candidates without modifying them."""

    root = _canonical(saturn_root)
    if not root.is_dir():
        raise SaturnStandaloneCandidateError(
            f"Saturn development root is not a directory: {root}"
        )
    if candidate_limit <= 0:
        raise SaturnStandaloneCandidateError("candidate_limit must be positive")

    libraries: list[Path] = []
    support_objects: list[Path] = []
    candidates: list[SaturnStandaloneProjectCandidate] = []

    for current, files in _walk(root):
        paths = tuple((current / filename).resolve() for filename in files)
        parts = tuple(part.casefold() for part in current.parts)
        inside_library_directory = any(part.startswith("lib") for part in parts)

        for path in paths:
            folded = path.name.casefold()
            if inside_library_directory and path.suffix.casefold() in _LIBRARY_SUFFIXES:
                libraries.append(path)
            if folded in _SUPPORT_OBJECT_NAMES:
                support_objects.append(path)

        makefiles = _unique_sorted(path for path in paths if _is_makefile(path.name))
        ip_candidates = [path for path in paths if path.name.casefold() == "ip.bin"]
        sources = _unique_sorted(
            path for path in paths if path.suffix.casefold() in _SOURCE_SUFFIXES
        )
        linker_files = _unique_sorted(
            path for path in paths if path.suffix.casefold() in _LINKER_SUFFIXES
        )
        startup_files = _unique_sorted(
            path for path in paths if path.name.casefold() in _STARTUP_NAMES
        )

        # Candidate directories must contain source plus at least one concrete
        # build/boot signal.  This keeps arbitrary asset directories out.
        if not sources or not (makefiles or ip_candidates):
            continue

        ip_bin = ip_candidates[0] if ip_candidates else None
        score, evidence = _score_candidate(
            current.resolve(),
            makefiles=makefiles,
            ip_bin=ip_bin,
            sources=sources,
            linker_files=linker_files,
            startup_files=startup_files,
        )
        candidates.append(
            SaturnStandaloneProjectCandidate(
                directory=current.resolve(),
                makefiles=makefiles,
                ip_bin=ip_bin,
                source_files=sources,
                linker_files=linker_files,
                startup_files=startup_files,
                score=score,
                evidence=evidence,
            )
        )

    ranked = tuple(
        sorted(
            candidates,
            key=lambda item: (-item.score, str(item.directory).casefold()),
        )[:candidate_limit]
    )

    return SaturnStandaloneCandidateReport(
        root=root,
        libraries=_unique_sorted(libraries),
        support_objects=_unique_sorted(support_objects),
        candidates=ranked,
    )
