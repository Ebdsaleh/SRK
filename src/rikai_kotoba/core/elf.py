"""Read-only ELF object decoding for SRK/Mjolnir.

The parser is intentionally self-contained and does not invoke objdump, nm, BFD,
or any compiler tool.  It supports ordinary ELF32/ELF64 files in either byte
order, including section tables and symbol tables.  Bounds are checked before
all table reads so malformed research inputs fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass


ELF_MAGIC = b"\x7fELF"
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_DYNSYM = 11
SHN_UNDEF = 0
SHN_ABS = 0xFFF1
SHN_COMMON = 0xFFF2


class ElfFormatError(ValueError):
    """Raised when bytes do not contain a supported, structurally valid ELF."""


@dataclass(frozen=True)
class ElfSection:
    index: int
    name: str
    section_type: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_size: int


@dataclass(frozen=True)
class ElfSymbol:
    name: str
    value: int
    size: int
    binding: str
    symbol_type: str
    visibility: int
    section_index: int
    section_name: str
    defined: bool


@dataclass(frozen=True)
class ElfObject:
    elf_class: int
    byte_order: str
    object_type: int
    machine: int
    entry_point: int
    sections: tuple[ElfSection, ...]
    symbols: tuple[ElfSymbol, ...]

    @property
    def format_name(self) -> str:
        return f"elf{self.elf_class}"

    @property
    def architecture(self) -> str:
        return {
            3: "x86",
            40: "ARM",
            42: "SH",
            62: "x86-64",
            183: "AArch64",
        }.get(self.machine, f"machine-{self.machine}")


@dataclass(frozen=True)
class _RawSection:
    name_offset: int
    section_type: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_size: int


def _bounded_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(data) or offset + size > len(data):
        raise ElfFormatError(
            f"{label} extends beyond ELF object: offset=0x{offset:X} size=0x{size:X} "
            f"object=0x{len(data):X}"
        )
    return data[offset : offset + size]


def _cstring(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return f"<bad-string-offset-0x{offset:X}>"
    end = data.find(b"\x00", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("utf-8", errors="replace")


def _binding_name(value: int) -> str:
    return {0: "LOCAL", 1: "GLOBAL", 2: "WEAK"}.get(value, f"BIND-{value}")


def _symbol_type_name(value: int) -> str:
    return {
        0: "NOTYPE",
        1: "OBJECT",
        2: "FUNC",
        3: "SECTION",
        4: "FILE",
        5: "COMMON",
        6: "TLS",
    }.get(value, f"TYPE-{value}")


def _parse_raw_sections(
    data: bytes,
    *,
    elf_class: int,
    byte_order: str,
    section_offset: int,
    section_entry_size: int,
    section_count: int,
) -> list[_RawSection]:
    expected = 40 if elf_class == 32 else 64
    if section_count == 0:
        return []
    if section_entry_size < expected:
        raise ElfFormatError(
            f"ELF section entry size {section_entry_size} is smaller than {expected}"
        )
    _bounded_slice(
        data,
        section_offset,
        section_entry_size * section_count,
        "section table",
    )

    raw: list[_RawSection] = []
    endian = byte_order
    for index in range(section_count):
        base = section_offset + index * section_entry_size
        entry = data[base : base + section_entry_size]
        if elf_class == 32:
            raw.append(
                _RawSection(
                    name_offset=int.from_bytes(entry[0:4], endian),
                    section_type=int.from_bytes(entry[4:8], endian),
                    flags=int.from_bytes(entry[8:12], endian),
                    address=int.from_bytes(entry[12:16], endian),
                    offset=int.from_bytes(entry[16:20], endian),
                    size=int.from_bytes(entry[20:24], endian),
                    link=int.from_bytes(entry[24:28], endian),
                    info=int.from_bytes(entry[28:32], endian),
                    alignment=int.from_bytes(entry[32:36], endian),
                    entry_size=int.from_bytes(entry[36:40], endian),
                )
            )
        else:
            raw.append(
                _RawSection(
                    name_offset=int.from_bytes(entry[0:4], endian),
                    section_type=int.from_bytes(entry[4:8], endian),
                    flags=int.from_bytes(entry[8:16], endian),
                    address=int.from_bytes(entry[16:24], endian),
                    offset=int.from_bytes(entry[24:32], endian),
                    size=int.from_bytes(entry[32:40], endian),
                    link=int.from_bytes(entry[40:44], endian),
                    info=int.from_bytes(entry[44:48], endian),
                    alignment=int.from_bytes(entry[48:56], endian),
                    entry_size=int.from_bytes(entry[56:64], endian),
                )
            )
    return raw


def _section_name_table(data: bytes, raw: list[_RawSection], index: int) -> bytes:
    if not raw or index == SHN_UNDEF:
        return b""
    if index < 0 or index >= len(raw):
        raise ElfFormatError(f"ELF section-name string-table index {index} is out of range")
    section = raw[index]
    if section.section_type != SHT_STRTAB:
        raise ElfFormatError("ELF section-name table does not reference a string-table section")
    return _bounded_slice(data, section.offset, section.size, "section-name string table")


def _parse_symbols(
    data: bytes,
    *,
    elf_class: int,
    byte_order: str,
    raw_sections: list[_RawSection],
    sections: tuple[ElfSection, ...],
) -> tuple[ElfSymbol, ...]:
    symbols: list[ElfSymbol] = []
    minimum_entry = 16 if elf_class == 32 else 24

    for table in raw_sections:
        if table.section_type not in {SHT_SYMTAB, SHT_DYNSYM}:
            continue
        entry_size = table.entry_size or minimum_entry
        if entry_size < minimum_entry:
            raise ElfFormatError("ELF symbol entry is smaller than the required structure")
        if table.size % entry_size:
            raise ElfFormatError("ELF symbol table size is not a whole number of entries")
        if table.link < 0 or table.link >= len(raw_sections):
            raise ElfFormatError("ELF symbol table links to an invalid string table")
        string_section = raw_sections[table.link]
        if string_section.section_type != SHT_STRTAB:
            raise ElfFormatError("ELF symbol table link does not reference a string table")
        strings = _bounded_slice(
            data,
            string_section.offset,
            string_section.size,
            "symbol string table",
        )
        table_bytes = _bounded_slice(data, table.offset, table.size, "symbol table")

        for offset in range(0, len(table_bytes), entry_size):
            entry = table_bytes[offset : offset + entry_size]
            if elf_class == 32:
                name_offset = int.from_bytes(entry[0:4], byte_order)
                value = int.from_bytes(entry[4:8], byte_order)
                size = int.from_bytes(entry[8:12], byte_order)
                info = entry[12]
                other = entry[13]
                section_index = int.from_bytes(entry[14:16], byte_order)
            else:
                name_offset = int.from_bytes(entry[0:4], byte_order)
                info = entry[4]
                other = entry[5]
                section_index = int.from_bytes(entry[6:8], byte_order)
                value = int.from_bytes(entry[8:16], byte_order)
                size = int.from_bytes(entry[16:24], byte_order)

            name = _cstring(strings, name_offset) if name_offset else ""
            if section_index == SHN_UNDEF:
                section_name = "UND"
                defined = False
            elif section_index == SHN_ABS:
                section_name = "ABS"
                defined = True
            elif section_index == SHN_COMMON:
                section_name = "COMMON"
                defined = True
            elif 0 <= section_index < len(sections):
                section_name = sections[section_index].name or f"#{section_index}"
                defined = True
            else:
                section_name = f"#{section_index}"
                defined = True

            symbols.append(
                ElfSymbol(
                    name=name,
                    value=value,
                    size=size,
                    binding=_binding_name(info >> 4),
                    symbol_type=_symbol_type_name(info & 0x0F),
                    visibility=other & 0x03,
                    section_index=section_index,
                    section_name=section_name,
                    defined=defined,
                )
            )
    return tuple(symbols)


def parse_elf(data: bytes) -> ElfObject:
    """Parse one ordinary ELF object from bytes."""

    if len(data) < 16 or data[:4] != ELF_MAGIC:
        raise ElfFormatError("missing ELF magic")
    if data[4] not in (1, 2):
        raise ElfFormatError(f"unsupported ELF class byte {data[4]}")
    if data[5] not in (1, 2):
        raise ElfFormatError(f"unsupported ELF data byte {data[5]}")

    elf_class = 32 if data[4] == 1 else 64
    byte_order = "little" if data[5] == 1 else "big"
    header_size = 52 if elf_class == 32 else 64
    if len(data) < header_size:
        raise ElfFormatError(f"ELF{elf_class} header is truncated")

    object_type = int.from_bytes(data[16:18], byte_order)
    machine = int.from_bytes(data[18:20], byte_order)
    if elf_class == 32:
        entry_point = int.from_bytes(data[24:28], byte_order)
        section_offset = int.from_bytes(data[32:36], byte_order)
        declared_header_size = int.from_bytes(data[40:42], byte_order)
        section_entry_size = int.from_bytes(data[46:48], byte_order)
        section_count = int.from_bytes(data[48:50], byte_order)
        shstr_index = int.from_bytes(data[50:52], byte_order)
    else:
        entry_point = int.from_bytes(data[24:32], byte_order)
        section_offset = int.from_bytes(data[40:48], byte_order)
        declared_header_size = int.from_bytes(data[52:54], byte_order)
        section_entry_size = int.from_bytes(data[58:60], byte_order)
        section_count = int.from_bytes(data[60:62], byte_order)
        shstr_index = int.from_bytes(data[62:64], byte_order)

    if declared_header_size and declared_header_size < header_size:
        raise ElfFormatError("ELF header-size field is smaller than the required header")
    if section_count and not section_offset:
        raise ElfFormatError("ELF declares sections but has no section-table offset")

    raw_sections = _parse_raw_sections(
        data,
        elf_class=elf_class,
        byte_order=byte_order,
        section_offset=section_offset,
        section_entry_size=section_entry_size,
        section_count=section_count,
    )
    name_table = _section_name_table(data, raw_sections, shstr_index)

    sections = tuple(
        ElfSection(
            index=index,
            name=_cstring(name_table, raw.name_offset) if name_table and raw.name_offset else "",
            section_type=raw.section_type,
            flags=raw.flags,
            address=raw.address,
            offset=raw.offset,
            size=raw.size,
            link=raw.link,
            info=raw.info,
            alignment=raw.alignment,
            entry_size=raw.entry_size,
        )
        for index, raw in enumerate(raw_sections)
    )

    for section in sections:
        if section.section_type != 8 and section.size:
            _bounded_slice(data, section.offset, section.size, f"section {section.name or section.index}")

    symbols = _parse_symbols(
        data,
        elf_class=elf_class,
        byte_order=byte_order,
        raw_sections=raw_sections,
        sections=sections,
    )

    return ElfObject(
        elf_class=elf_class,
        byte_order=byte_order,
        object_type=object_type,
        machine=machine,
        entry_point=entry_point,
        sections=sections,
        symbols=symbols,
    )
