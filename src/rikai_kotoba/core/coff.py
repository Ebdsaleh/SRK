"""Read-only COFF decoding for SRK/Mjolnir.

The Saturn SDK contains Hitachi SuperH COFF objects alongside ELF objects.  This
module parses those objects directly from bytes: file headers, section headers,
string tables, and symbols.  It never invokes BFD/binutils and never rewrites or
converts SDK files.
"""

from __future__ import annotations

from dataclasses import dataclass


COFF_FILE_HEADER_SIZE = 20
COFF_SECTION_HEADER_SIZE = 40
COFF_SYMBOL_ENTRY_SIZE = 18
SH_COFF_MAGIC_BIG = 0x0500
SH_COFF_MAGIC_LITTLE = 0x0550
COFF_SCNUM_UNDEFINED = 0
COFF_SCNUM_ABSOLUTE = -1
COFF_SCNUM_DEBUG = -2


class CoffFormatError(ValueError):
    """Raised when bytes do not contain a supported, structurally valid COFF."""


@dataclass(frozen=True)
class CoffFileHeader:
    architecture: str
    byte_order: str
    magic: int
    section_count: int
    timestamp: int
    symbol_table_offset: int
    symbol_count: int
    optional_header_size: int
    flags: int
    symbol_table_end: int

    @property
    def format_name(self) -> str:
        return "coff-sh"

    @property
    def detail(self) -> str:
        return (
            f"Hitachi SH {self.byte_order}-endian COFF "
            f"magic=0x{self.magic:04X} sections={self.section_count} "
            f"symbols={self.symbol_count}"
        )


@dataclass(frozen=True)
class CoffSection:
    index: int
    name: str
    physical_address: int
    virtual_address: int
    size: int
    data_offset: int
    relocation_offset: int
    line_number_offset: int
    relocation_count: int
    line_number_count: int
    flags: int


@dataclass(frozen=True)
class CoffSymbol:
    index: int
    name: str
    value: int
    section_number: int
    section_name: str
    symbol_type: int
    storage_class: int
    auxiliary_count: int
    defined: bool
    external: bool


@dataclass(frozen=True)
class CoffObject:
    header: CoffFileHeader
    sections: tuple[CoffSection, ...]
    symbols: tuple[CoffSymbol, ...]

    @property
    def format_name(self) -> str:
        return self.header.format_name

    @property
    def architecture(self) -> str:
        return self.header.architecture

    @property
    def byte_order(self) -> str:
        return self.header.byte_order


def _byte_order_for_magic(data: bytes) -> tuple[str, int]:
    if len(data) < 2:
        raise CoffFormatError("COFF header is shorter than the 2-byte magic")

    if data[:2] == b"\x05\x00":
        return "big", SH_COFF_MAGIC_BIG
    if data[:2] == b"\x50\x05":
        return "little", SH_COFF_MAGIC_LITTLE
    raise CoffFormatError(
        "unsupported COFF magic: " + " ".join(f"{value:02X}" for value in data[:2])
    )


def _bounded_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(data) or offset + size > len(data):
        raise CoffFormatError(
            f"{label} extends beyond COFF object: offset=0x{offset:X} size=0x{size:X} "
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


def parse_coff_file_header(
    data: bytes,
    *,
    total_size: int | None = None,
) -> CoffFileHeader:
    """Decode a Hitachi SH COFF file header from raw bytes."""

    if len(data) < COFF_FILE_HEADER_SIZE:
        raise CoffFormatError(
            f"COFF header requires {COFF_FILE_HEADER_SIZE} bytes; got {len(data)}"
        )

    byte_order, magic = _byte_order_for_magic(data)
    endian = byte_order
    section_count = int.from_bytes(data[2:4], endian)
    timestamp = int.from_bytes(data[4:8], endian)
    symbol_table_offset = int.from_bytes(data[8:12], endian)
    symbol_count = int.from_bytes(data[12:16], endian)
    optional_header_size = int.from_bytes(data[16:18], endian)
    flags = int.from_bytes(data[18:20], endian)
    symbol_table_end = symbol_table_offset + symbol_count * COFF_SYMBOL_ENTRY_SIZE

    if section_count <= 0:
        raise CoffFormatError("SH COFF object declares no sections")
    if total_size is not None:
        if total_size < COFF_FILE_HEADER_SIZE:
            raise CoffFormatError("COFF object is smaller than its file header")
        section_table_end = (
            COFF_FILE_HEADER_SIZE
            + optional_header_size
            + section_count * COFF_SECTION_HEADER_SIZE
        )
        if section_table_end > total_size:
            raise CoffFormatError("COFF section table extends beyond the object")
        if symbol_count:
            if symbol_table_offset < section_table_end:
                raise CoffFormatError("COFF symbol table overlaps the file/section headers")
            if symbol_table_end > total_size:
                raise CoffFormatError(
                    "COFF symbol table extends beyond the object: "
                    f"0x{symbol_table_end:X} > 0x{total_size:X}"
                )
        elif symbol_table_offset > total_size:
            raise CoffFormatError(
                "COFF symbol-table offset extends beyond the object: "
                f"0x{symbol_table_offset:X} > 0x{total_size:X}"
            )

    return CoffFileHeader(
        architecture="Hitachi SH",
        byte_order=byte_order,
        magic=magic,
        section_count=section_count,
        timestamp=timestamp,
        symbol_table_offset=symbol_table_offset,
        symbol_count=symbol_count,
        optional_header_size=optional_header_size,
        flags=flags,
        symbol_table_end=symbol_table_end,
    )


def _short_name(field: bytes) -> str:
    return field.split(b"\x00", 1)[0].decode("ascii", errors="replace").rstrip()


def _parse_sections(data: bytes, header: CoffFileHeader) -> tuple[CoffSection, ...]:
    start = COFF_FILE_HEADER_SIZE + header.optional_header_size
    size = header.section_count * COFF_SECTION_HEADER_SIZE
    table = _bounded_slice(data, start, size, "COFF section table")
    endian = header.byte_order
    sections: list[CoffSection] = []

    for zero_index in range(header.section_count):
        entry = table[
            zero_index * COFF_SECTION_HEADER_SIZE : (zero_index + 1) * COFF_SECTION_HEADER_SIZE
        ]
        section = CoffSection(
            index=zero_index + 1,
            name=_short_name(entry[0:8]),
            physical_address=int.from_bytes(entry[8:12], endian),
            virtual_address=int.from_bytes(entry[12:16], endian),
            size=int.from_bytes(entry[16:20], endian),
            data_offset=int.from_bytes(entry[20:24], endian),
            relocation_offset=int.from_bytes(entry[24:28], endian),
            line_number_offset=int.from_bytes(entry[28:32], endian),
            relocation_count=int.from_bytes(entry[32:34], endian),
            line_number_count=int.from_bytes(entry[34:36], endian),
            flags=int.from_bytes(entry[36:40], endian),
        )
        if section.data_offset and section.size:
            _bounded_slice(
                data,
                section.data_offset,
                section.size,
                f"COFF section {section.name or section.index}",
            )
        sections.append(section)
    return tuple(sections)


def _string_table(data: bytes, header: CoffFileHeader) -> bytes:
    if not header.symbol_count:
        return b""
    if header.symbol_table_end + 4 > len(data):
        return b""
    length = int.from_bytes(
        data[header.symbol_table_end : header.symbol_table_end + 4],
        header.byte_order,
    )
    if length < 4:
        raise CoffFormatError("COFF string table length is smaller than its length field")
    return _bounded_slice(data, header.symbol_table_end, length, "COFF string table")


def _symbol_name(field: bytes, strings: bytes, byte_order: str) -> str:
    if field[0:4] == b"\x00\x00\x00\x00":
        offset = int.from_bytes(field[4:8], byte_order)
        if offset == 0:
            return ""
        return _cstring(strings, offset)
    return _short_name(field)


def _section_label(number: int, sections: tuple[CoffSection, ...]) -> tuple[str, bool]:
    if number == COFF_SCNUM_UNDEFINED:
        return "UND", False
    if number == COFF_SCNUM_ABSOLUTE:
        return "ABS", True
    if number == COFF_SCNUM_DEBUG:
        return "DEBUG", True
    if 1 <= number <= len(sections):
        return sections[number - 1].name or f"#{number}", True
    return f"#{number}", True


def _parse_symbols(
    data: bytes,
    header: CoffFileHeader,
    sections: tuple[CoffSection, ...],
) -> tuple[CoffSymbol, ...]:
    if not header.symbol_count:
        return ()
    table = _bounded_slice(
        data,
        header.symbol_table_offset,
        header.symbol_count * COFF_SYMBOL_ENTRY_SIZE,
        "COFF symbol table",
    )
    strings = _string_table(data, header)
    endian = header.byte_order
    symbols: list[CoffSymbol] = []
    index = 0

    while index < header.symbol_count:
        base = index * COFF_SYMBOL_ENTRY_SIZE
        entry = table[base : base + COFF_SYMBOL_ENTRY_SIZE]
        name = _symbol_name(entry[0:8], strings, endian)
        value = int.from_bytes(entry[8:12], endian)
        section_number = int.from_bytes(entry[12:14], endian, signed=True)
        symbol_type = int.from_bytes(entry[14:16], endian)
        storage_class = entry[16]
        auxiliary_count = entry[17]
        if index + auxiliary_count >= header.symbol_count:
            raise CoffFormatError("COFF symbol auxiliary records extend past the symbol table")
        section_name, defined = _section_label(section_number, sections)
        symbols.append(
            CoffSymbol(
                index=index,
                name=name,
                value=value,
                section_number=section_number,
                section_name=section_name,
                symbol_type=symbol_type,
                storage_class=storage_class,
                auxiliary_count=auxiliary_count,
                defined=defined,
                external=storage_class in {2, 105},
            )
        )
        index += 1 + auxiliary_count
    return tuple(symbols)


def parse_coff(data: bytes) -> CoffObject:
    """Parse one Hitachi SH COFF object, including sections and symbols."""

    header = parse_coff_file_header(data, total_size=len(data))
    sections = _parse_sections(data, header)
    symbols = _parse_symbols(data, header, sections)
    return CoffObject(header=header, sections=sections, symbols=symbols)
