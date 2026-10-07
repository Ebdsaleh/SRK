"""Read-only discovery for the upstream SAROO ``Firm_Saturn`` build tools.

The upstream SAROO Makefile expects an SH-ELF cross toolchain plus a few Unix-
style support utilities. SRK must not silently mutate the user's global PATH or
pretend a build environment is ready when one of those programs is missing, so
discovery is explicit and reports where every resolved executable came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
from typing import Iterable


class SarooToolchainError(RuntimeError):
    """Raised when an explicit SAROO toolchain search root is invalid."""


@dataclass(frozen=True)
class SarooToolRequirement:
    name: str
    aliases: tuple[str, ...]
    purpose: str


SAROO_TOOL_REQUIREMENTS: tuple[SarooToolRequirement, ...] = (
    SarooToolRequirement(
        "sh-elf-gcc",
        ("sh-elf-gcc", "sh-elf-gcc.exe"),
        "SuperH C compiler used by Firm_Saturn",
    ),
    SarooToolRequirement(
        "sh-elf-as",
        ("sh-elf-as", "sh-elf-as.exe"),
        "SuperH assembler used by Firm_Saturn",
    ),
    SarooToolRequirement(
        "sh-elf-objdump",
        ("sh-elf-objdump", "sh-elf-objdump.exe"),
        "SuperH object/disassembly inspector used by the Makefile",
    ),
    SarooToolRequirement(
        "sh-elf-objcopy",
        ("sh-elf-objcopy", "sh-elf-objcopy.exe"),
        "SuperH object converter used to publish the Saturn binary",
    ),
    SarooToolRequirement(
        "make",
        (
            "make",
            "make.exe",
            "gmake",
            "gmake.exe",
            "mingw32-make",
            "mingw32-make.exe",
        ),
        "Make-compatible build driver for the upstream Firm_Saturn Makefile",
    ),
    SarooToolRequirement(
        "touch",
        ("touch", "touch.exe"),
        "File timestamp utility invoked by the upstream Firm_Saturn Makefile",
    ),
    SarooToolRequirement(
        "cat",
        ("cat", "cat.exe"),
        "Binary concatenation utility invoked by the upstream Firm_Saturn Makefile",
    ),
    SarooToolRequirement(
        "rm",
        ("rm", "rm.exe"),
        "File removal utility invoked by the upstream Firm_Saturn Makefile",
    ),
)


@dataclass(frozen=True)
class SarooToolProbe:
    requirement: SarooToolRequirement
    resolved_path: Path | None
    source: str

    @property
    def available(self) -> bool:
        return self.resolved_path is not None


@dataclass(frozen=True)
class SarooToolchainReport:
    search_root: Path | None
    probes: tuple[SarooToolProbe, ...]

    @property
    def ready(self) -> bool:
        """Whether every required executable was resolved.

        This is a *discovery* result. A later build is still the authoritative
        proof that the compiler/linker installation is operational.
        """

        return all(probe.available for probe in self.probes)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            probe.requirement.name for probe in self.probes if not probe.available
        )

    def path_for(self, name: str) -> Path | None:
        wanted = str(name or "").strip().casefold()
        for probe in self.probes:
            if probe.requirement.name.casefold() == wanted:
                return probe.resolved_path
        return None


_SKIP_DIRECTORIES = {".git", ".svn", "__pycache__", "node_modules"}
_MAX_SEARCH_DEPTH = 6


def _canonical(path: os.PathLike[str] | str) -> Path:
    """Return one stable absolute filesystem spelling for a path.

    On Windows, environment variables such as TEMP may use an 8.3 short-name
    spelling (for example ``DEVELO~1.ERI``) while callers hold the equivalent
    long path. ``Path.resolve()`` asks Windows for the resolved filesystem path
    and prevents the same directory being reported under two spellings where
    Windows exposes the long form. Tests still compare filesystem identity
    rather than relying on one textual spelling.
    """

    return Path(path).expanduser().resolve(strict=False)


def _matching_file(directory: Path, aliases: Iterable[str]) -> Path | None:
    wanted = {name.casefold() for name in aliases}
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return None
    for entry in entries:
        try:
            if entry.is_file() and entry.name.casefold() in wanted:
                return entry.resolve()
        except OSError:
            continue
    return None


def _search_explicit_root(
    root: Path,
    requirement: SarooToolRequirement,
) -> Path | None:
    """Search an explicit SaturnOrbit/toolchain root without touching PATH."""

    preferred = (
        root,
        root / "bin",
        root / "sh-elf" / "bin",
        root / "toolchain" / "bin",
        root / "tools" / "bin",
        root / "SH_ELF" / "sh-elf" / "bin",
        root / "SH_ELF" / "Other Utilities",
    )
    checked: set[Path] = set()
    for directory in preferred:
        directory = directory.resolve()
        checked.add(directory)
        if directory.is_dir():
            match = _matching_file(directory, requirement.aliases)
            if match is not None:
                return match

    root_depth = len(root.parts)
    for current_text, directory_names, _file_names in os.walk(root):
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
        resolved = current.resolve()
        if resolved in checked:
            continue
        checked.add(resolved)
        match = _matching_file(current, requirement.aliases)
        if match is not None:
            return match
    return None


def _search_path(
    requirement: SarooToolRequirement,
    *,
    path_env: str | None,
) -> Path | None:
    search_path = os.environ.get("PATH", "") if path_env is None else path_env
    for alias in requirement.aliases:
        resolved = shutil.which(alias, path=search_path)
        if resolved:
            return _canonical(resolved)
    return None


def inspect_saroo_toolchain(
    toolchain_root: os.PathLike[str] | str | None = None,
    *,
    path_env: str | None = None,
) -> SarooToolchainReport:
    """Resolve every executable needed by upstream SAROO ``Firm_Saturn``.

    When ``toolchain_root`` is supplied it is searched first, including nested
    SaturnOrbit-style ``bin`` and ``Other Utilities`` directories. The process
    PATH is only *read* as a fallback and is never changed. ``path_env`` exists
    primarily so tests or callers can supply an explicit PATH snapshot.
    """

    root: Path | None = None
    if toolchain_root is not None:
        root = _canonical(toolchain_root)
        if not root.is_dir():
            raise SarooToolchainError(
                f"SAROO toolchain search root is not a directory: {root}"
            )

    probes: list[SarooToolProbe] = []
    for requirement in SAROO_TOOL_REQUIREMENTS:
        resolved: Path | None = None
        source = "missing"

        if root is not None:
            resolved = _search_explicit_root(root, requirement)
            if resolved is not None:
                source = "toolchain-root"

        if resolved is None:
            resolved = _search_path(requirement, path_env=path_env)
            if resolved is not None:
                source = "PATH"

        probes.append(
            SarooToolProbe(
                requirement=requirement,
                resolved_path=resolved,
                source=source,
            )
        )

    return SarooToolchainReport(search_root=root, probes=tuple(probes))
