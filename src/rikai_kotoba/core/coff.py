"""Minimal read-only COFF header decoding for SRK binary research.

The initial consumer is Mjolnir's Saturn SBL investigation.  The parser is
intentionally narrow: it recognizes the documented Hitachi SuperH COFF file
header and exposes only fields that can be proven from the raw bytes.  It does
not invoke BFD/binutils and it does not rewrite or convert object files.
"""

from __future__ import annotations

from dataclasses import dataclass


COFF_FILE_HEADER_SIZE = 20
COFF_SYMBOL_ENTRY_SIZE = 18
SH_COFF_MAGIC_BIG = 0x0500
SH_COFF_MAGIC_LITTLE = 0x0550


class CoffFormatError(ValueError):
    """Raised when bytes do not contain a supported COFF file header."""


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


def parse_coff_file_header(
    data: bytes,
    *,
    total_size: int | None = None,
) -> CoffFileHeader:
    """Decode a Hitachi SH COFF file header from raw bytes.

    ``total_size`` is optional because callers may only have a member prefix. If
    provided, the symbol-table range is checked against the enclosing object.
    """

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
        if symbol_table_offset > total_size:
            raise CoffFormatError(
                "COFF symbol-table offset extends beyond the object: "
                f"0x{symbol_table_offset:X} > 0x{total_size:X}"
            )
        if symbol_count and symbol_table_end > total_size:
            raise CoffFormatError(
                "COFF symbol table extends beyond the object: "
                f"0x{symbol_table_end:X} > 0x{total_size:X}"
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
