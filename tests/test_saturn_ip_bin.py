"""Synthetic tests for Sega Saturn IP.BIN parsing and metadata patching."""

import os
import tempfile
import unittest

from rikai_kotoba.formats.saturn.ip_bin import (
    SaturnIPBinError,
    parse_ip_bin,
    parse_saturn_system_id,
    patch_saturn_system_id,
)


SECTOR = 2048


def _field(text, size):
    return text.encode("ascii").ljust(size, b" ")


def _put_u32be(data, offset, value):
    data[offset : offset + 4] = int(value).to_bytes(4, byteorder="big", signed=False)


def _boot_sector():
    data = bytearray(SECTOR)
    data[0x00:0x10] = _field("SEGA SEGASATURN", 16)
    data[0x10:0x20] = _field("SEGA ENTERPRISES", 16)
    data[0x20:0x2A] = _field("T-0000G", 10)
    data[0x2A:0x30] = _field("V1.000", 6)
    data[0x30:0x38] = _field("20261009", 8)
    data[0x38:0x40] = _field("CD-1/1", 8)
    data[0x40:0x4A] = _field("JTUE", 10)
    data[0x4A:0x50] = b" " * 6
    data[0x50:0x60] = _field("J", 16)
    data[0x60:0xD0] = _field("GENERIC TEST DISC", 112)

    _put_u32be(data, 0xE0, 0x00001800)
    _put_u32be(data, 0xE8, 0x06002000)
    _put_u32be(data, 0xEC, 0x06003000)
    _put_u32be(data, 0xF0, 0x06004000)
    _put_u32be(data, 0xF4, 0x00012345)
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
        self.assertEqual(metadata["product_number"], "T-0000G")
        self.assertEqual(metadata["game_serial"], "T-0000G")
        self.assertEqual(metadata["game_version"], "V1.000")
        self.assertEqual(metadata["game_date"], "20261009")
        self.assertEqual(metadata["device_info"], "CD-1/1")
        self.assertEqual(metadata["area_symbols"], "JTUE")
        self.assertEqual(metadata["peripherals"], "J")
        self.assertEqual(metadata["game_title"], "GENERIC TEST DISC")

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
            self.assertEqual(metadata["product_number"], "T-0000G")

    def test_parses_big_endian_boot_control_fields(self):
        metadata = parse_saturn_system_id(_boot_sector())

        self.assertEqual(metadata["ip_size"], "0x00001800")
        self.assertEqual(metadata["master_stack"], "0x06002000")
        self.assertEqual(metadata["slave_stack"], "0x06003000")
        self.assertEqual(metadata["first_read_address"], "0x06004000")
        self.assertEqual(metadata["first_read_size"], "0x00012345")

    def test_patch_changes_only_selected_system_id_fields(self):
        source = bytearray(_boot_sector())
        source[0xD0:0xE0] = bytes(range(16))
        source[0x100:0x110] = b"BOOTSTRAP-PAYLOAD"
        source = bytes(source)

        patched = patch_saturn_system_id(
            source,
            maker_id="SRK PROJECT",
            product_number="SRK-DIAG",
            game_version="V0.001",
            game_date="20261009",
            area_symbols="JTUE",
            peripherals="J",
            game_title="SRK SATURN DIAGNOSTICS",
            first_read_address=0x06004000,
            first_read_size=0,
        )
        metadata = parse_saturn_system_id(patched)

        self.assertEqual(metadata["maker_id"], "SRK PROJECT")
        self.assertEqual(metadata["product_number"], "SRK-DIAG")
        self.assertEqual(metadata["game_title"], "SRK SATURN DIAGNOSTICS")
        self.assertEqual(metadata["first_read_address"], "0x06004000")
        self.assertEqual(metadata["first_read_size"], "0x00000000")
        self.assertEqual(patched[0x00:0x10], source[0x00:0x10])
        self.assertEqual(patched[0xD0:0xE0], source[0xD0:0xE0])
        self.assertEqual(patched[0xE0:0xF0], source[0xE0:0xF0])
        self.assertEqual(patched[0x100:], source[0x100:])
        self.assertEqual(source[0x10:0x20], _field("SEGA ENTERPRISES", 16))

    def test_patch_rejects_non_ascii_or_oversize_fields(self):
        with self.assertRaises(SaturnIPBinError):
            patch_saturn_system_id(_boot_sector(), game_title="SRK ♥")
        with self.assertRaises(SaturnIPBinError):
            patch_saturn_system_id(_boot_sector(), product_number="TOO-LONG-123")


if __name__ == "__main__":
    unittest.main()
