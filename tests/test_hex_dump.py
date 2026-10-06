"""Tests for generic SRK hexadecimal dump formatting."""

import os
import tempfile
import unittest

from rikai_kotoba.core.hex_dump import (
    format_hexdump_line,
    hexdump_text,
    iter_hexdump_lines,
    write_hexdump,
)


class HexDumpTests(unittest.TestCase):
    def test_formats_standard_hex_and_ascii_columns(self):
        line = format_hexdump_line(0x20, b"ABC\x00\x7f")
        self.assertTrue(line.startswith("00000020: 41 42 43 00 7F"))
        self.assertTrue(line.endswith("ABC.."))

    def test_iterates_with_logical_offsets(self):
        lines = list(iter_hexdump_lines(bytes(range(20)), start_offset=0x100))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("00000100:"))
        self.assertTrue(lines[1].startswith("00000110:"))

    def test_text_is_empty_for_empty_input(self):
        self.assertEqual(hexdump_text(b""), "")

    def test_write_refuses_existing_output_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "dump.hex")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("keep")

            with self.assertRaises(FileExistsError):
                write_hexdump(b"replacement", path)

            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "keep")

    def test_explicit_overwrite_replaces_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "dump.hex")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("old")

            write_hexdump(b"A", path, overwrite=True)

            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("41", text)
            self.assertIn("A", text)
            self.assertNotIn("old", text)


if __name__ == "__main__":
    unittest.main()
