"""Synthetic command-line tests for the public SRK CLI."""

from contextlib import redirect_stderr, redirect_stdout
import io
import os
import tempfile
import unittest

from rikai_kotoba.cli import main


SECTOR = 2048


def _record(name, lba, size, is_dir=False):
    if name == ".":
        identifier = b"\x00"
    elif name == "..":
        identifier = b"\x01"
    else:
        identifier = name.encode("ascii")

    length = 33 + len(identifier)
    if length % 2:
        length += 1

    record = bytearray(length)
    record[0] = length
    record[2:6] = lba.to_bytes(4, "little")
    record[6:10] = lba.to_bytes(4, "big")
    record[10:14] = size.to_bytes(4, "little")
    record[14:18] = size.to_bytes(4, "big")
    record[25] = 0x02 if is_dir else 0
    record[28:30] = (1).to_bytes(2, "little")
    record[30:32] = (1).to_bytes(2, "big")
    record[32] = len(identifier)
    record[33 : 33 + len(identifier)] = identifier
    return bytes(record)


def _field(text, size):
    return text.encode("ascii").ljust(size, b" ")


def _make_test_iso(path):
    image = bytearray(SECTOR * 40)

    boot = bytearray(SECTOR)
    boot[0:16] = _field("SEGA SEGASATURN", 16)
    boot[16:32] = _field("SEGA ENTERPRISES", 16)
    boot[32:48] = _field("CD-1/1", 16)
    boot[48:56] = _field("JTUB", 8)
    boot[56:72] = _field("J", 16)
    boot[72:112] = _field("GENERIC CLI TEST", 40)
    boot[112:128] = _field("V1.000", 16)
    boot[128:144] = _field("19960101", 16)
    boot[144:160] = _field("T-0000G", 16)
    image[0:SECTOR] = boot

    root_lba = 20
    pvd = bytearray(SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01
    root_record = _record(".", root_lba, SECTOR, True)
    pvd[156 : 156 + len(root_record)] = root_record
    image[16 * SECTOR : 17 * SECTOR] = pvd

    root = bytearray(SECTOR)
    records = [
        _record(".", root_lba, SECTOR, True),
        _record("..", root_lba, SECTOR, True),
        _record("HELLO.TXT;1", 30, 5, False),
    ]
    offset = 0
    for record in records:
        root[offset : offset + len(record)] = record
        offset += len(record)
    image[root_lba * SECTOR : (root_lba + 1) * SECTOR] = root
    image[30 * SECTOR : 30 * SECTOR + 5] = b"hello"

    with open(path, "wb") as handle:
        handle.write(image)


class CLITests(unittest.TestCase):
    def test_list_files_accepts_user_supplied_image_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = os.path.join(temp_dir, "sample.iso")
            _make_test_iso(image)
            output = io.StringIO()

            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                result = main(["list-files", image])

            self.assertEqual(result, 0)
            self.assertIn("/HELLO.TXT", output.getvalue())

    def test_inspect_saturn_uses_logical_disc_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = os.path.join(temp_dir, "sample.iso")
            _make_test_iso(image)
            output = io.StringIO()

            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                result = main(["inspect-saturn", image])

            self.assertEqual(result, 0)
            self.assertIn("GENERIC CLI TEST", output.getvalue())

    def test_extract_one_file_uses_safe_extractor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = os.path.join(temp_dir, "sample.iso")
            output_root = os.path.join(temp_dir, "out")
            _make_test_iso(image)

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = main(
                    ["extract", image, output_root, "--file", "/HELLO.TXT"]
                )

            self.assertEqual(result, 0)
            with open(os.path.join(output_root, "HELLO.TXT"), "rb") as handle:
                self.assertEqual(handle.read(), b"hello")

    def test_correlate_reports_exact_source_to_memory_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.bin")
            dump = os.path.join(temp_dir, "ram.bin")
            with open(source, "wb") as handle:
                handle.write(b"ABCDEFGH" + b"IJKLMNOP")
            with open(dump, "wb") as handle:
                handle.write(b"----" + b"ABCDEFGH" + b"IJKLMNOP" + b"----")

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                result = main(
                    [
                        "correlate",
                        source,
                        dump,
                        "--base-address",
                        "0x06000000",
                        "--chunk-size",
                        "8",
                        "--minimum-chunk-size",
                        "8",
                    ]
                )

            rendered = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn("0x06000004", rendered)
            self.assertIn("0x00000010", rendered)
            self.assertIn("2 matched", rendered)


if __name__ == "__main__":
    unittest.main()
