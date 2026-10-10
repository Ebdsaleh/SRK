"""Normalized read-only object-file inspection for SRK/Mjolnir.

ELF and Hitachi SH COFF objects expose the same section/symbol vocabulary here,
so higher-level tools can search symbols and dependency relationships without
caring which historical toolchain produced each object.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from rikai_kotoba.core.binary_archive import (
    ArchiveMember,
    BinaryArchiveError,
    inspect_binary,
)
from rikai_kotoba.core.coff import CoffFormatError, parse_coff
from rikai_kotoba.core.elf import ELF_MAGIC, ElfFormatError, parse_elf


class ObjectFormatError(ValueError):
    """Raised when an object format is unsupported or structurally invalid."""


@dataclass(frozen=True)
class ObjectSection:
    index: int
    name: str
    section_type: str
    address: int
    offset: int
    size: int
    flags: int


@dataclass(frozen=True)
class ObjectSymbol:
    name: str
    value: int
    size: int
    section: str
    defined: bool
    global_symbol: bool
    weak: bool
    kind: str
    raw_class: str


@dataclass(frozen=True)
class ObjectInspection:
    format_name: str
    architecture: str
    byte_order: str
    sections: tuple[ObjectSection, ...]
    symbols: tuple[ObjectSymbol, ...]

    @property
    def defined_symbols(self) -> tuple[ObjectSymbol, ...]:
        return tuple(
            symbol
            for symbol in self.symbols
            if symbol.name and symbol.defined and (symbol.global_symbol or symbol.weak)
        )

    @property
    def undefined_symbols(self) -> tuple[ObjectSymbol, ...]:
        return tuple(
            symbol
            for symbol in self.symbols
            if symbol.name and not symbol.defined and (symbol.global_symbol or symbol.weak)
        )


@dataclass(frozen=True)
class ArchiveObjectInspection:
    archive_path: Path
    member: ArchiveMember
    object: ObjectInspection | None
    error: str | None


def _coff_object(data: bytes) -> ObjectInspection:
    parsed = parse_coff(data)
    sections = tuple(
        ObjectSection(
            index=section.index,
            name=section.name,
            section_type="COFF",
            address=section.virtual_address,
            offset=section.data_offset,
            size=section.size,
            flags=section.flags,
        )
        for section in parsed.sections
    )
    symbols = tuple(
        ObjectSymbol(
            name=symbol.name,
            value=symbol.value,
            size=0,
            section=symbol.section_name,
            defined=symbol.defined,
            global_symbol=symbol.external,
            weak=symbol.storage_class == 105,
            kind=f"TYPE-0x{symbol.symbol_type:04X}",
            raw_class=f"COFF-C{symbol.storage_class}",
        )
        for symbol in parsed.symbols
    )
    return ObjectInspection(
        format_name="coff-sh",
        architecture=parsed.architecture,
        byte_order=parsed.byte_order,
        sections=sections,
        symbols=symbols,
    )


def _elf_object(data: bytes) -> ObjectInspection:
    parsed = parse_elf(data)
    sections = tuple(
        ObjectSection(
            index=section.index,
            name=section.name,
            section_type=f"ELF-SHT-{section.section_type}",
            address=section.address,
            offset=section.offset,
            size=section.size,
            flags=section.flags,
        )
        for section in parsed.sections
    )
    symbols = tuple(
        ObjectSymbol(
            name=symbol.name,
            value=symbol.value,
            size=symbol.size,
            section=symbol.section_name,
            defined=symbol.defined,
            global_symbol=symbol.binding == "GLOBAL",
            weak=symbol.binding == "WEAK",
            kind=symbol.symbol_type,
            raw_class=symbol.binding,
        )
        for symbol in parsed.symbols
    )
    return ObjectInspection(
        format_name=parsed.format_name,
        architecture=parsed.architecture,
        byte_order=parsed.byte_order,
        sections=sections,
        symbols=symbols,
    )


def inspect_object_bytes(data: bytes) -> ObjectInspection:
    """Inspect a supported object file from bytes without external tools."""

    try:
        if data.startswith(ELF_MAGIC):
            return _elf_object(data)
        if data[:2] in {b"\x05\x00", b"\x50\x05"}:
            return _coff_object(data)
    except (ElfFormatError, CoffFormatError) as exc:
        raise ObjectFormatError(str(exc)) from exc
    raise ObjectFormatError("unsupported object-file signature")


def inspect_object_file(path: str | Path) -> ObjectInspection:
    source = Path(path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise ObjectFormatError(f"object inspection source is not a file: {source}")
    return inspect_object_bytes(source.read_bytes())


def _read_member_bytes(path: Path, member: ArchiveMember) -> bytes:
    with path.open("rb") as handle:
        handle.seek(member.data_offset)
        data = handle.read(member.size)
    if len(data) != member.size:
        raise BinaryArchiveError(
            f"archive member {member.name} truncated while reading payload"
        )
    return data


def inspect_archive_objects(path: str | Path) -> tuple[ArchiveObjectInspection, ...]:
    """Inspect every payload object in one classic Unix archive read-only."""

    source = Path(path).expanduser().resolve(strict=False)
    report = inspect_binary(source)
    if report.container_kind != "unix-ar":
        raise BinaryArchiveError(f"not a classic Unix ar archive: {source}")

    objects: list[ArchiveObjectInspection] = []
    for member in report.members:
        if member.metadata:
            continue
        try:
            payload = _read_member_bytes(source, member)
            parsed = inspect_object_bytes(payload)
        except (OSError, BinaryArchiveError, ObjectFormatError) as exc:
            objects.append(
                ArchiveObjectInspection(
                    archive_path=source,
                    member=member,
                    object=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            objects.append(
                ArchiveObjectInspection(
                    archive_path=source,
                    member=member,
                    object=parsed,
                    error=None,
                )
            )
    return tuple(objects)


def iter_external_symbols(
    objects: Iterable[ArchiveObjectInspection],
) -> Iterable[tuple[ArchiveObjectInspection, ObjectSymbol]]:
    for record in objects:
        if record.object is None:
            continue
        for symbol in record.object.symbols:
            if symbol.name and (symbol.global_symbol or symbol.weak):
                yield record, symbol
