"""Tests for Mjolnir's self-contained ELF decoder."""

import unittest

from rikai_kotoba.core.elf import ElfFormatError, parse_elf


def _section_header(
    name: int,
    section_type: int,
    flags: int,
    offset: int,
    size: int,
    *,
    link: int = 0,
    info: int = 0,
    align: int = 1,
    entsize: int = 0,
) -> bytes:
    values = (
        name,
        section_type,
        flags,
        0,
        offset,
        size,
        link,
        info,
        align,
        entsize,
    )
    return b"".join(value.to_bytes(4, "big") for value in values)


def elf32_sh_fixture() -> bytes:
    data = bytearray(0x300)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 2
    data[6] = 1
    data[16:18] = (1).to_bytes(2, "big")
    data[18:20] = (42).to_bytes(2, "big")
    data[20:24] = (1).to_bytes(4, "big")
    data[32:36] = (0x200).to_bytes(4, "big")
    data[40:42] = (52).to_bytes(2, "big")
    data[46:48] = (40).to_bytes(2, "big")
    data[48:50] = (5).to_bytes(2, "big")
    data[50:52] = (4).to_bytes(2, "big")

    data[0x100:0x104] = b"\x00\x09\x00\x09"
    strings = b"\x00foo\x00bar\x00"
    data[0x110 : 0x110 + len(strings)] = strings
    shstrings = b"\x00.text\x00.strtab\x00.symtab\x00.shstrtab\x00"
    data[0x180 : 0x180 + len(shstrings)] = shstrings

    # Null symbol.
    sym = bytearray(48)
    # foo: global function in .text.
    sym[16:20] = (1).to_bytes(4, "big")
    sym[20:24] = (0).to_bytes(4, "big")
    sym[24:28] = (4).to_bytes(4, "big")
    sym[28] = 0x12
    sym[30:32] = (1).to_bytes(2, "big")
    # bar: global undefined.
    sym[32:36] = (5).to_bytes(4, "big")
    sym[44] = 0x10
    sym[46:48] = (0).to_bytes(2, "big")
    data[0x140:0x170] = sym

    sh = bytearray()
    sh += bytes(40)
    sh += _section_header(1, 1, 0x6, 0x100, 4, align=4)
    sh += _section_header(7, 3, 0, 0x110, len(strings))
    sh += _section_header(15, 2, 0, 0x140, 48, link=2, info=1, align=4, entsize=16)
    sh += _section_header(23, 3, 0, 0x180, len(shstrings))
    data[0x200 : 0x200 + len(sh)] = sh
    return bytes(data)


class ElfTests(unittest.TestCase):
    def test_parses_elf32_big_endian_sh_sections_and_symbols(self):
        parsed = parse_elf(elf32_sh_fixture())

        self.assertEqual(parsed.format_name, "elf32")
        self.assertEqual(parsed.architecture, "SH")
        self.assertEqual(parsed.byte_order, "big")
        self.assertEqual(parsed.sections[1].name, ".text")
        self.assertEqual(parsed.sections[3].name, ".symtab")

        foo = next(symbol for symbol in parsed.symbols if symbol.name == "foo")
        bar = next(symbol for symbol in parsed.symbols if symbol.name == "bar")
        self.assertTrue(foo.defined)
        self.assertEqual(foo.binding, "GLOBAL")
        self.assertEqual(foo.symbol_type, "FUNC")
        self.assertEqual(foo.section_name, ".text")
        self.assertFalse(bar.defined)
        self.assertEqual(bar.section_name, "UND")

    def test_rejects_section_table_past_end(self):
        raw = bytearray(elf32_sh_fixture())
        raw[32:36] = (0x2F0).to_bytes(4, "big")
        with self.assertRaises(ElfFormatError):
            parse_elf(bytes(raw))


if __name__ == "__main__":
    unittest.main()
