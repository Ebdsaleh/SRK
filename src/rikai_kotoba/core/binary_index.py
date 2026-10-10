"""Cross-file symbol indexing for Mjolnir binary research.

This layer turns supported ELF/COFF objects and Unix archives into a searchable
symbol database.  It is format-neutral and read-only: callers can scan SDK
library directories, locate symbol providers/consumers, and derive dependency
relationships without invoking nm/objdump/linkers or extracting archives.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rikai_kotoba.core.binary_archive import BinaryArchiveError, inspect_binary
from rikai_kotoba.core.object_file import (
    ObjectFormatError,
    ObjectInspection,
    ObjectSymbol,
    inspect_archive_objects,
    inspect_object_file,
)


_BINARY_SUFFIXES = {
    ".a",
    ".lib",
    ".o",
    ".obj",
    ".elf",
    ".axf",
    ".out",
}


@dataclass(frozen=True)
class BinaryObjectUnit:
    source_path: Path
    member_name: str | None
    object: ObjectInspection

    @property
    def display_name(self) -> str:
        if self.member_name:
            return f"{self.source_path}({self.member_name})"
        return str(self.source_path)


@dataclass(frozen=True)
class BinaryScanError:
    path: Path
    detail: str


@dataclass(frozen=True)
class SymbolLocation:
    source_path: Path
    member_name: str | None
    object_format: str
    symbol: ObjectSymbol

    @property
    def display_name(self) -> str:
        if self.member_name:
            return f"{self.source_path}({self.member_name})"
        return str(self.source_path)


@dataclass(frozen=True)
class SymbolDependency:
    symbol: str
    consumer: SymbolLocation
    providers: tuple[SymbolLocation, ...]


@dataclass(frozen=True)
class BinarySymbolIndex:
    units: tuple[BinaryObjectUnit, ...]
    errors: tuple[BinaryScanError, ...]
    providers: dict[str, tuple[SymbolLocation, ...]]
    consumers: dict[str, tuple[SymbolLocation, ...]]
    dependencies: tuple[SymbolDependency, ...]

    @property
    def unresolved(self) -> tuple[SymbolDependency, ...]:
        return tuple(item for item in self.dependencies if not item.providers)


def _candidate_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    iterator = path.rglob("*") if recursive else path.glob("*")
    return sorted(
        candidate
        for candidate in iterator
        if candidate.is_file() and candidate.suffix.casefold() in _BINARY_SUFFIXES
    )


def discover_binary_candidates(
    paths: Sequence[str | Path],
    *,
    recursive: bool = False,
) -> tuple[Path, ...]:
    """Return deterministic candidate files from explicit files/directories."""

    found: dict[str, Path] = {}
    for supplied in paths:
        path = Path(supplied).expanduser().resolve(strict=False)
        for candidate in _candidate_files(path, recursive):
            found[str(candidate).casefold()] = candidate
    return tuple(found[key] for key in sorted(found))


def _units_from_file(path: Path) -> tuple[list[BinaryObjectUnit], list[BinaryScanError]]:
    units: list[BinaryObjectUnit] = []
    errors: list[BinaryScanError] = []
    try:
        report = inspect_binary(path)
    except (OSError, BinaryArchiveError) as exc:
        return [], [BinaryScanError(path, f"{type(exc).__name__}: {exc}")]

    if report.container_kind == "unix-ar":
        try:
            records = inspect_archive_objects(path)
        except (OSError, BinaryArchiveError) as exc:
            return [], [BinaryScanError(path, f"{type(exc).__name__}: {exc}")]
        for record in records:
            if record.object is None:
                errors.append(
                    BinaryScanError(
                        path,
                        f"{record.member.name}: {record.error or 'unsupported object'}",
                    )
                )
                continue
            units.append(
                BinaryObjectUnit(
                    source_path=path,
                    member_name=record.member.name,
                    object=record.object,
                )
            )
        return units, errors

    try:
        parsed = inspect_object_file(path)
    except (OSError, ObjectFormatError) as exc:
        errors.append(BinaryScanError(path, f"{type(exc).__name__}: {exc}"))
    else:
        units.append(BinaryObjectUnit(source_path=path, member_name=None, object=parsed))
    return units, errors


def scan_binary_objects(
    paths: Sequence[str | Path],
    *,
    recursive: bool = False,
) -> tuple[tuple[BinaryObjectUnit, ...], tuple[BinaryScanError, ...]]:
    """Scan supported candidate files into normalized object units."""

    candidates = discover_binary_candidates(paths, recursive=recursive)
    units: list[BinaryObjectUnit] = []
    errors: list[BinaryScanError] = []
    for path in candidates:
        file_units, file_errors = _units_from_file(path)
        units.extend(file_units)
        errors.extend(file_errors)
    return tuple(units), tuple(errors)


def _location(unit: BinaryObjectUnit, symbol: ObjectSymbol) -> SymbolLocation:
    return SymbolLocation(
        source_path=unit.source_path,
        member_name=unit.member_name,
        object_format=unit.object.format_name,
        symbol=symbol,
    )


def build_symbol_index(
    paths: Sequence[str | Path],
    *,
    recursive: bool = False,
) -> BinarySymbolIndex:
    """Build provider/consumer/dependency indexes across supported binaries."""

    units, errors = scan_binary_objects(paths, recursive=recursive)
    provider_lists: dict[str, list[SymbolLocation]] = {}
    consumer_lists: dict[str, list[SymbolLocation]] = {}

    for unit in units:
        for symbol in unit.object.symbols:
            if not symbol.name or not (symbol.global_symbol or symbol.weak):
                continue
            target = provider_lists if symbol.defined else consumer_lists
            target.setdefault(symbol.name, []).append(_location(unit, symbol))

    providers = {
        name: tuple(locations)
        for name, locations in sorted(provider_lists.items())
    }
    consumers = {
        name: tuple(locations)
        for name, locations in sorted(consumer_lists.items())
    }

    dependencies: list[SymbolDependency] = []
    for symbol_name, locations in consumers.items():
        matches = providers.get(symbol_name, ())
        for consumer in locations:
            dependencies.append(
                SymbolDependency(
                    symbol=symbol_name,
                    consumer=consumer,
                    providers=matches,
                )
            )

    return BinarySymbolIndex(
        units=units,
        errors=errors,
        providers=providers,
        consumers=consumers,
        dependencies=tuple(dependencies),
    )


def find_symbols(
    index: BinarySymbolIndex,
    query: str,
    *,
    exact: bool = False,
) -> tuple[tuple[str, tuple[SymbolLocation, ...], tuple[SymbolLocation, ...]], ...]:
    """Find symbols by exact or case-insensitive substring match."""

    needle = query.casefold()
    names = sorted(set(index.providers) | set(index.consumers))
    matches = []
    for name in names:
        matched = name.casefold() == needle if exact else needle in name.casefold()
        if matched:
            matches.append(
                (
                    name,
                    index.providers.get(name, ()),
                    index.consumers.get(name, ()),
                )
            )
    return tuple(matches)


def library_dependency_edges(
    index: BinarySymbolIndex,
) -> dict[tuple[Path, Path], tuple[str, ...]]:
    """Collapse resolved symbol dependencies into source-file dependency edges."""

    edges: dict[tuple[Path, Path], set[str]] = {}
    for dependency in index.dependencies:
        for provider in dependency.providers:
            if provider.source_path == dependency.consumer.source_path:
                continue
            key = (dependency.consumer.source_path, provider.source_path)
            edges.setdefault(key, set()).add(dependency.symbol)
    return {
        key: tuple(sorted(symbols))
        for key, symbols in sorted(
            edges.items(),
            key=lambda item: (str(item[0][0]).casefold(), str(item[0][1]).casefold()),
        )
    }
