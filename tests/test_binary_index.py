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
from tests.binary_fixtures import ar_member, coff_sh_fixture, elf32_sh_fixture


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
                b"!<arch>\n" + ar_member("consumer.o/", elf32_sh_fixture())
            )
            coff_archive.write_bytes(
                b"!<arch>\n"
                + ar_member(
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
                + ar_member("sample.o/", coff_sh_fixture(defined_name="DMA_ScuStart"))
            )
            index = build_symbol_index([path])
            matches = find_symbols(index, "scustart")

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0][0], "DMA_ScuStart")
            self.assertEqual(len(matches[0][1]), 1)


if __name__ == "__main__":
    unittest.main()
