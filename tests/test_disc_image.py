"""Tests for the generic SRK disc-image safety and geometry layer."""

import os
import tempfile
import unittest

from rikai_kotoba.core.disc_image import (
    DiscImage,
    MODE1_2048,
    MODE1_2352,
    MODE2_2352_FORM1,
    UnsafeOutputPathError,
)


class DiscImageTests(unittest.TestCase):
    def _make_image(self, path, geometry, sectors=20):
        blob = bytearray(geometry.sector_size * sectors)

        for lba in range(sectors):
            start = geometry.physical_offset(lba)
            payload = bytes([lba & 0xFF]) * geometry.user_data_size
            blob[start : start + geometry.user_data_size] = payload

        pvd = geometry.physical_offset(16)
        blob[pvd] = 0x01
        blob[pvd + 1 : pvd + 6] = b"CD001"
        blob[pvd + 6] = 0x01

        with open(path, "wb") as handle:
            handle.write(blob)

    def test_detects_supported_geometries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for index, geometry in enumerate(
                (MODE1_2048, MODE1_2352, MODE2_2352_FORM1)
            ):
                with self.subTest(geometry=geometry.name):
                    path = os.path.join(temp_dir, f"image_{index}.bin")
                    self._make_image(path, geometry)
                    image = DiscImage(path)
                    self.assertEqual(image.geometry, geometry)
                    self.assertEqual(image.read_lba(3), bytes([3]) * 2048)

    def test_read_extent_trims_sector_padding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "image.bin")
            self._make_image(path, MODE1_2352)
            image = DiscImage(path)

            data = image.read_file_extent(2, 2500)
            self.assertEqual(len(data), 2500)
            self.assertEqual(data[:2048], bytes([2]) * 2048)
            self.assertEqual(data[2048:], bytes([3]) * (2500 - 2048))

    def test_source_path_is_never_accepted_as_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "image.bin")
            self._make_image(path, MODE1_2048)
            image = DiscImage(path)

            with self.assertRaises(UnsafeOutputPathError):
                image.create_output_copy(path)

    def test_output_copy_preserves_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.bin")
            output = os.path.join(temp_dir, "out", "copy.bin")
            self._make_image(source, MODE1_2352)

            with open(source, "rb") as handle:
                before = handle.read()

            image = DiscImage(source)
            created = image.create_output_copy(output)

            with open(source, "rb") as handle:
                after = handle.read()
            with open(created, "rb") as handle:
                copied = handle.read()

            self.assertEqual(before, after)
            self.assertEqual(before, copied)

    def test_existing_output_is_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.bin")
            output = os.path.join(temp_dir, "copy.bin")
            self._make_image(source, MODE1_2048)
            self._make_image(output, MODE1_2048)

            image = DiscImage(source)
            with self.assertRaises(FileExistsError):
                image.create_output_copy(output)


if __name__ == "__main__":
    unittest.main()
