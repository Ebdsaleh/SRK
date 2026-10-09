"""Read-only discovery for SRK's standalone Sega Saturn build environment.

The standalone diagnostics program deliberately does not assume that the SAROO
firmware build layout is also the user's Saturn CD/homebrew build layout.  This
module inventories an explicit Saturn development root and reports the concrete
compiler, SGL, sample, IP.BIN, and packaging assets that are actually present.

Discovery never edits the supplied tree or mutates PATH.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
from typing import Iterable

from .saroo.toolchain import SarooToolchainReport, inspect_saroo_toolchain


class SaturnStandaloneEnvironmentError(RuntimeError):
    """Raised when the requested standalone Saturn environment cannot be probed."""


@dataclass(frozen=True)
class SaturnStandaloneToolRequirement:
    key: str
    aliases: tuple[str, ...]
    purpose: str


STANDALONE_TOOL_REQUIREMENTS: tuple[SaturnStandaloneToolRequirement, ...] = (
    SaturnStandaloneToolRequirement(
        "make",
        ("make", "make.exe", "mingw32-make", "mingw32-make.exe"),
        "sample/build orchestration",
    ),
    SaturnStandaloneToolRequirement(
        "iso-builder",
        ("mkisofs", "mkisofs.exe", "genisoimage", "genisoimage.exe", "xorriso", "xorriso.exe"),
        "bootable ISO construction",
    ),
    SaturnStandaloneToolRequirement(
        "ip-builder",
        ("IPMaker", "IPMaker.exe", "ipmaker", "ipmaker.exe", "makeip", "makeip.exe"),
        "Saturn IP.BIN construction",
    ),
)


@dataclass(frozen=True)
class SaturnStandaloneToolProbe:
    requirement: SaturnStandaloneToolRequirement
    resolved_path: Path | None
    source: str

    @property
    def available(self) -> bool:
        return self.resolved_path is not None


@dataclass(frozen=True)
class SaturnStandaloneEnvironmentReport:
    root: Path
    compiler: SarooToolchainReport
    sgl_roots: tuple[Path, ...]
    sgl_headers: tuple[Path, ...]
    libraries: tuple[Path, ...]
    sample_makefiles: tuple[Path, ...]
    ip_bin_assets: tuple[Path, ...]
    tools: tuple[SaturnStandaloneToolProbe, ...]

    @property
    def compiler_ready(self) -> bool:
        return self.compiler.ready

    @property
    def sgl_detected(self) -> bool:
        return bool(self.sgl_roots and self.sgl_headers)

    @property
    def samples_detected(self) -> bool:
        return bool(self.sample_makefiles)

    @property
    def ip_asset_detected(self) -> bool:
        return bool(self.ip_bin_assets)

    def tool_for(self, key: str) -> SaturnStandaloneToolProbe | None:
        wanted = str(key or "").strip().casefold()
        for probe in self.tools:
            if probe.requirement.key.casefold() == wanted:
                return probe
        return None


_SKIP_DIRECTORIES = {".git", ".svn", "__pycache__", "node_modules"}
_MAX_SEARCH_DEPTH = 7
_MAX_SAMPLE_MAKEFILES = 25


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _walk(root: Path, *, max_depth: int = _MAX_SEARCH_DEPTH):
    root_depth = len(root.parts)
    for current_text, directory_names, file_names in os.walk(root):
        current = Path(current_text)
        depth = len(current.parts) - root_depth
        directory_names[:] = sorted(
            (
                name
                for name in directory_names
                if name not in _SKIP_DIRECTORIES and depth < max_depth
            ),
            key=str.casefold,
        )
        yield current, tuple(directory_names), tuple(sorted(file_names, key=str.casefold))


def _root_tool(root: Path, aliases: Iterable[str]) -> Path | None:
    wanted = {alias.casefold() for alias in aliases}
    preferred = (
        root,
        root / "bin",
        root / "MinGW" / "bin",
        root / "tools",
        root / "tools" / "bin",
        root / "toolchain" / "bin",
    )
    checked: set[Path] = set()

    for directory in preferred:
        resolved = directory.resolve(strict=False)
        checked.add(resolved)
        if not directory.is_dir():
            continue
        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.is_file() and entry.name.casefold() in wanted:
                    return entry.resolve()
            except OSError:
                continue

    for current, _directories, files in _walk(root):
        resolved = current.resolve(strict=False)
        if resolved in checked:
            continue
        for filename in files:
            if filename.casefold() in wanted:
                candidate = current / filename
                try:
                    if candidate.is_file():
                        return candidate.resolve()
                except OSError:
                    pass
    return None


def _path_tool(aliases: Iterable[str], *, path_env: str | None) -> Path | None:
    search_path = os.environ.get("PATH", "") if path_env is None else path_env
    for alias in aliases:
        resolved = shutil.which(alias, path=search_path)
        if resolved:
            return _canonical(resolved)
    return None


def _probe_tools(root: Path, *, path_env: str | None) -> tuple[SaturnStandaloneToolProbe, ...]:
    probes: list[SaturnStandaloneToolProbe] = []
    for requirement in STANDALONE_TOOL_REQUIREMENTS:
        resolved = _root_tool(root, requirement.aliases)
        source = "saturn-root" if resolved is not None else "missing"
        if resolved is None:
            resolved = _path_tool(requirement.aliases, path_env=path_env)
            if resolved is not None:
                source = "PATH"
        probes.append(
            SaturnStandaloneToolProbe(
                requirement=requirement,
                resolved_path=resolved,
                source=source,
            )
        )
    return tuple(probes)


def inspect_saturn_standalone_environment(
    saturn_root: os.PathLike[str] | str,
    *,
    path_env: str | None = None,
    sample_limit: int = _MAX_SAMPLE_MAKEFILES,
) -> SaturnStandaloneEnvironmentReport:
    """Inventory one Saturn development root without modifying it.

    ``sample_limit`` caps only the number of sample Makefiles returned in the
    report.  Discovery itself remains bounded by ``_MAX_SEARCH_DEPTH`` so an
    accidentally broad root cannot turn into an unbounded filesystem crawl.
    """

    root = _canonical(saturn_root)
    if not root.is_dir():
        raise SaturnStandaloneEnvironmentError(
            f"Saturn development root is not a directory: {root}"
        )
    if sample_limit <= 0:
        raise SaturnStandaloneEnvironmentError("sample_limit must be positive")

    # Reuse the already-tested SH-ELF resolver, while keeping this probe read-only.
    compiler = inspect_saroo_toolchain(root, path_env=path_env)

    sgl_roots: list[Path] = []
    sgl_headers: list[Path] = []
    libraries: list[Path] = []
    sample_makefiles: list[Path] = []
    ip_bin_assets: list[Path] = []

    for current, directories, files in _walk(root):
        if current.name.casefold() == "sgl_302j":
            sgl_roots.append(current.resolve())

        lowered_parts = {part.casefold() for part in current.parts}
        inside_sgl = "sgl_302j" in lowered_parts
        inside_sample = "sample" in lowered_parts or "samples" in lowered_parts
        inside_lib = "lib" in lowered_parts or "lib32" in lowered_parts

        for filename in files:
            folded = filename.casefold()
            candidate = (current / filename).resolve()
            if inside_sgl and folded == "sl_def.h":
                sgl_headers.append(candidate)
            if inside_sgl and inside_lib and folded.endswith(".a"):
                libraries.append(candidate)
            if inside_sample and folded in {"makefile", "makefile.mk"}:
                sample_makefiles.append(candidate)
            if folded == "ip.bin":
                ip_bin_assets.append(candidate)

        # A directory named SGL_302j can occur at the search-depth boundary;
        # record it even when os.walk will not descend further.
        for dirname in directories:
            if dirname.casefold() == "sgl_302j":
                sgl_roots.append((current / dirname).resolve())

    def unique_sorted(paths: Iterable[Path]) -> tuple[Path, ...]:
        unique = {str(path).casefold(): path for path in paths}
        return tuple(sorted(unique.values(), key=lambda path: str(path).casefold()))

    samples = unique_sorted(sample_makefiles)[:sample_limit]

    return SaturnStandaloneEnvironmentReport(
        root=root,
        compiler=compiler,
        sgl_roots=unique_sorted(sgl_roots),
        sgl_headers=unique_sorted(sgl_headers),
        libraries=unique_sorted(libraries),
        sample_makefiles=samples,
        ip_bin_assets=unique_sorted(ip_bin_assets),
        tools=_probe_tools(root, path_env=path_env),
    )
