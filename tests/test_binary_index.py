"""Tests for Mjolnir's format-neutral object and dependency index."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.core.binary_index import (
    build_symbol_index,
    find_symbols,
    library_dependency_edges,
)
from rikai_kotoba.core.object_file import inspect_object_bytes
from test_elf import elf32_sh_fixture


def _ar_member(name: str, payload: bytes) -> bytes:
    header = (
        name.encode("ascii").ljust(16, b" ")
        + b"0".ljust(12, b" ")
        + b"0".ljust(6, b" ")
        + b"0".ljust(6, b" ")
        + b"100644".ljust(8, b" ")
        + str(len(payload)).encode("ascii").ljust(10, b" ")
        + b"`\n"
    )
    return header + payload + (b"\n" if len(payload) & 1 else b"")


def coff_sh_fixture(*, defined_name: str = "bar", undefined_name: str = "baz") -> bytes:
    symptr = 0x80
    symbol_count = 2
    total = symptr + symbol_count * 18 + 4
    data = bytearray(total)
    data[0:2] = (0x0500).to_bytes(2, "big")
    data[2:4] = (1).to_bytes(2, "big")
    data[8:12] = symptr.to_bytes(4, "big")
    data[12:16] = symbol_count.to_bytes(4, "big")

    section = bytearray(40)
    section[0:8] = b".text\x00\x00\x00"
    section[16:20] = (4).to_bytes(4, "big")
    section[20:24] = (0x60).to_bytes(4, "big")
    section[36:40] = (0x20).to_bytes(4, "big")
    data[20:60] = section
    data[0x60:0x64] = b"\x00\x09\x00\x09"

    def symbol(name: str, section_number: int) -> bytes:
        encoded = name.encode("ascii")
        if len(encoded) > 8:
            raise AssertionError("fixture uses short COFF names")
        return b"".join(
            (
                encoded.ljust(8, b"\x00"),
                (0).to_bytes(4, "big"),
                section_number.to_bytes(2, "big", signed=True),
                (0x20).to_bytes(2, "big"),
                bytes((2, 0)),
            )
        )

    data[symptr : symptr + 18] = symbol(defined_name, 1)
    data[symptr + 18 : symptr + 36] = symbol(undefined_name, 0)
    data[symptr + 36 : symptr + 40] = (4).to_bytes(4, "big")
    return bytes(data)


class BinaryIndexTests(unittest.TestCase):
    def test_normalized_object_layer_decodes_hitachi_sh_coff_symbols(self):
        parsed = inspect_object_bytes(coff_sh_fixture())

        self.assertEqual(parsed.format_name, "coff-sh")
        self.assertEqual(parsed.architecture, "Hitachi SH")
        self.assertEqual(parsed.sections[0].name, ".text")
        self.assertEqual([symbol.name for symbol in parsed.defined_symbols], ["bar"])
        self.assertEqual([symbol.name for symbol in parsed.undefined_symbols], ["baz"])

    def test_index_resolves_symbols_across_elf_and_coff_archives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            elf_archive = root / "consumer.a"
            coff_archive = root / "provider.a"
            elf_archive.write_bytes(
                b"!<arch>\n" + _ar_member("consumer.o/", elf32_sh_fixture())
            )
            coff_archive.write_bytes(
                b"!<arch>\n"
                + _ar_member(
                    "provider.o/",
                    coff_sh_fixture(defined_name="bar", undefined_name="other"),
                )
            )

            index = build_symbol_index([root], recursive=True)

            self.assertEqual(len(index.units), 2)
            self.assertIn("bar", index.providers)
            self.assertIn("bar", index.consumers)
            bar_dependency = next(item for item in index.dependencies if item.symbol == "bar")
            self.assertEqual(len(bar_dependency.providers), 1)
            self.assertEqual(bar_dependency.providers[0].source_path, coff_archive.resolve())
            self.assertIn("other", {item.symbol for item in index.unresolved})

            edges = library_dependency_edges(index)
            self.assertIn((elf_archive.resolve(), coff_archive.resolve()), edges)
            self.assertEqual(edges[(elf_archive.resolve(), coff_archive.resolve())], ("bar",))

    def test_symbol_search_reports_providers_and_consumers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.a"
            path.write_bytes(
                b"!<arch>\n"
                + _ar_member("sample.o/", coff_sh_fixture(defined_name="DMA_ScuStart"))
            )
            index = build_symbol_index([path])
            matches = find_symbols(index, "scustart")

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0][0], "DMA_ScuStart")
            self.assertEqual(len(matches[0][1]), 1)


if __name__ == "__main__":
    unittest.main()
