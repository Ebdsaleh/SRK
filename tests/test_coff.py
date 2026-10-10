"""Tests for SRK's minimal read-only Hitachi SH COFF decoder."""

import unittest

from rikai_kotoba.core.coff import (
    COFF_SYMBOL_ENTRY_SIZE,
    CoffFormatError,
    SH_COFF_MAGIC_BIG,
    SH_COFF_MAGIC_LITTLE,
    parse_coff_file_header,
)


def _header(
    *,
    byte_order: str,
    magic: int,
    sections: int = 3,
    timestamp: int = 0x30E308FD,
    symptr: int = 0x56C,
    symbols: int = 0x21,
    optional: int = 0,
    flags: int = 0,
) -> bytes:
    return b"".join(
        (
            magic.to_bytes(2, byte_order),
            sections.to_bytes(2, byte_order),
            timestamp.to_bytes(4, byte_order),
            symptr.to_bytes(4, byte_order),
            symbols.to_bytes(4, byte_order),
            optional.to_bytes(2, byte_order),
            flags.to_bytes(2, byte_order),
        )
    )


class CoffTests(unittest.TestCase):
    def test_decodes_big_endian_hitachi_sh_header(self):
        raw = _header(byte_order="big", magic=SH_COFF_MAGIC_BIG)
        header = parse_coff_file_header(raw, total_size=0x1000)

        self.assertEqual(header.format_name, "coff-sh")
        self.assertEqual(header.architecture, "Hitachi SH")
        self.assertEqual(header.byte_order, "big")
        self.assertEqual(header.magic, 0x0500)
        self.assertEqual(header.section_count, 3)
        self.assertEqual(header.symbol_table_offset, 0x56C)
        self.assertEqual(header.symbol_count, 0x21)
        self.assertEqual(
            header.symbol_table_end,
            0x56C + 0x21 * COFF_SYMBOL_ENTRY_SIZE,
        )
        self.assertIn("Hitachi SH big-endian COFF", header.detail)

    def test_decodes_little_endian_hitachi_sh_header(self):
        raw = _header(
            byte_order="little",
            magic=SH_COFF_MAGIC_LITTLE,
            symptr=0x120,
            symbols=4,
        )
        header = parse_coff_file_header(raw, total_size=0x400)

        self.assertEqual(header.byte_order, "little")
        self.assertEqual(header.magic, 0x0550)
        self.assertEqual(header.symbol_table_offset, 0x120)
        self.assertEqual(header.symbol_count, 4)

    def test_rejects_unrecognized_magic(self):
        raw = bytearray(_header(byte_order="big", magic=SH_COFF_MAGIC_BIG))
        raw[0:2] = b"\x7fE"
        with self.assertRaises(CoffFormatError):
            parse_coff_file_header(bytes(raw), total_size=0x1000)

    def test_rejects_symbol_table_past_object_end(self):
        raw = _header(
            byte_order="big",
            magic=SH_COFF_MAGIC_BIG,
            symptr=0x100,
            symbols=16,
        )
        with self.assertRaises(CoffFormatError):
            parse_coff_file_header(raw, total_size=0x120)


if __name__ == "__main__":
    unittest.main()
