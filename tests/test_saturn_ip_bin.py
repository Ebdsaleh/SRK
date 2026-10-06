"""Synthetic tests for Sega Saturn IP.BIN parsing."""

import os
import tempfile
import unittest

from rikai_kotoba.formats.saturn.ip_bin import parse_ip_bin


SECTOR = 2048


def _field(text, size):
    return text.encode("ascii").ljust(size, b" ")


def _boot_sector():
    data = bytearray(SECTOR)
    data[0:16] = _field("SEGA SEGASATURN", 16)
    data[16:32] = _field("SEGA ENTERPRISES", 16)
    data[32:48] = _field("CD-1/1", 16)
    data[48:56] = _field("JTUB", 8)
    data[56:72] = _field("J", 16)
    data[72:112] = _field("GENERIC TEST DISC", 40)
    data[112:128] = _field("V1.000", 16)
    data[128:144] = _field("19960101", 16)
    data[144:160] = _field("T-0000G", 16)
    return bytes(data)


class _FakeSource:
    def read_lba(self, lba):
        if lba != 0:
            raise ValueError(lba)
        return _boot_sector()


class SaturnIPBinTests(unittest.TestCase):
    def test_parses_logical_source_without_raw_sector_assumptions(self):
        metadata = parse_ip_bin(_FakeSource())

        self.assertEqual(metadata["hardware_id"], "SEGA SEGASATURN")
        self.assertEqual(metadata["maker_id"], "SEGA ENTERPRISES")
        self.assertEqual(metadata["game_title"], "GENERIC TEST DISC")
        self.assertEqual(metadata["game_serial"], "T-0000G")

    def test_path_input_uses_generic_disc_source_layer(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "saturn-test.iso")
            image = bytearray(SECTOR * 20)
            image[0:SECTOR] = _boot_sector()
            image[16 * SECTOR + 1 : 16 * SECTOR + 6] = b"CD001"
            with open(path, "wb") as handle:
                handle.write(image)

            metadata = parse_ip_bin(path)

            self.assertEqual(metadata["game_title"], "GENERIC TEST DISC")
            self.assertEqual(metadata["game_version"], "V1.000")


if __name__ == "__main__":
    unittest.main()
