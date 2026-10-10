"""Tests for the non-interactive Mjolnir binary/archive workbench."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.tools.mjolnir_binary import main
from test_binary_index import coff_sh_fixture
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


class MjolnirBinaryTests(unittest.TestCase):
    def test_cli_reports_archive_read_only_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "sample.a"
            archive.write_bytes(b"!<arch>\n" + _ar_member("raw.o/", b"ABCD"))
            before = sorted(path.name for path in root.iterdir())
            output = StringIO()

            with redirect_stdout(output):
                result = main([str(archive)])

            after = sorted(path.name for path in root.iterdir())
            text = output.getvalue()
            self.assertEqual(result, 0)
            self.assertEqual(before, after)
            self.assertIn("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR", text)
            self.assertIn("Read-only    : yes", text)
            self.assertIn("Container    : unix-ar", text)
            self.assertIn("[000] raw.o", text)
            self.assertIn("Object errors : 1", text)

    def test_cli_accepts_multiple_inputs_for_side_by_side_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"FIRST")
            second.write_bytes(b"SECOND")
            output = StringIO()

            with redirect_stdout(output):
                result = main([str(first), str(second)])

            text = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn(str(first.resolve()), text)
            self.assertIn(str(second.resolve()), text)
            self.assertEqual(text.count("Read-only    : yes"), 2)

    def test_cli_reports_missing_input_as_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.a"
            output = StringIO()

            with redirect_stdout(output):
                result = main([str(missing)])

            self.assertEqual(result, 2)
            self.assertIn("Result       : ERROR", output.getvalue())

    def test_cli_recursively_resolves_mixed_elf_coff_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "LIB_ELF"
            nested.mkdir()
            (nested / "gfs.a").write_bytes(
                b"!<arch>\n" + _ar_member("gfs.o/", elf32_sh_fixture())
            )
            (nested / "support.a").write_bytes(
                b"!<arch>\n"
                + _ar_member("support.o/", coff_sh_fixture(defined_name="bar"))
            )
            output = StringIO()

            with redirect_stdout(output):
                result = main([str(root), "--recursive", "--dependencies"])

            text = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn("MJOLNIR SYMBOL DEPENDENCY ANALYSIS", text)
            self.assertIn("Resolved source-file dependency edges", text)
            self.assertIn("support.a", text)
            self.assertIn("bar", text)

    def test_cli_symbol_search_finds_exact_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "support.a"
            archive.write_bytes(
                b"!<arch>\n"
                + _ar_member("support.o/", coff_sh_fixture(defined_name="DMA_ScuStart"))
            )
            output = StringIO()

            with redirect_stdout(output):
                result = main(
                    [
                        str(root),
                        "--recursive",
                        "--search-symbol",
                        "DMA_ScuStart",
                        "--exact-symbol",
                    ]
                )

            text = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn("MJOLNIR SYMBOL SEARCH", text)
            self.assertIn("DMA_ScuStart: providers=1", text)
            self.assertIn("coff-sh", text)


if __name__ == "__main__":
    unittest.main()
