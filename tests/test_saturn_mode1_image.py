"""Tests for verified Saturn single-track MODE1/2352 BIN/CUE generation."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.formats.saturn.mode1_image import (
    RAW_SECTOR_BYTES,
    SaturnMode1ImageError,
    encode_mode1_sector,
    verify_mode1_bin_against_iso,
    write_single_track_mode1_bin_cue,
)


class SaturnMode1ImageTests(unittest.TestCase):
    def test_known_zero_sector_vector_has_standard_mode1_framing(self):
        sector = encode_mode1_sector(bytes(2048), 0)

        self.assertEqual(len(sector), 2352)
        self.assertEqual(sector[:12], b"\x00" + (b"\xff" * 10) + b"\x00")
        self.assertEqual(sector[12:16], bytes.fromhex("00020001"))
        self.assertEqual(sector[0x814:0x81C], b"\x00" * 8)
        self.assertEqual(
            sha256(sector).hexdigest(),
            "b4f18ab66709c9b3fdef2721cc323e031b6728f3ca6c57b7c435c96189222250",
        )

    def test_writes_single_track_bin_cue_and_roundtrips_iso_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iso = root / "source.iso"
            raw = root / "SRK-Diagnostics.bin"
            cue = root / "SRK-Diagnostics.cue"
            payload = bytes((index * 17) & 0xFF for index in range(4096))
            iso.write_bytes(payload)

            result = write_single_track_mode1_bin_cue(iso, raw, cue)

            self.assertEqual(result.sector_count, 2)
            self.assertEqual(result.user_bytes, 4096)
            self.assertEqual(result.raw_bytes, 2 * RAW_SECTOR_BYTES)
            self.assertEqual(verify_mode1_bin_against_iso(iso, raw), 2)
            self.assertEqual(
                cue.read_bytes(),
                b'FILE "SRK-Diagnostics.bin" BINARY\r\n'
                b"  TRACK 01 MODE1/2352\r\n"
                b"    INDEX 01 00:00:00\r\n",
            )

            raw_bytes = raw.read_bytes()
            self.assertEqual(raw_bytes[16:16 + 2048], payload[:2048])
            second = RAW_SECTOR_BYTES
            self.assertEqual(raw_bytes[second + 16:second + 16 + 2048], payload[2048:])
            self.assertEqual(raw_bytes[second + 12:second + 16], bytes.fromhex("00020101"))

    def test_verifier_rejects_tampered_raw_sector(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iso = root / "source.iso"
            raw = root / "disc.bin"
            cue = root / "disc.cue"
            iso.write_bytes(bytes(2048))
            write_single_track_mode1_bin_cue(iso, raw, cue)

            damaged = bytearray(raw.read_bytes())
            damaged[100] ^= 0x80
            raw.write_bytes(damaged)

            with self.assertRaises(SaturnMode1ImageError):
                verify_mode1_bin_against_iso(iso, raw)

    def test_rejects_non_sector_aligned_iso(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iso = root / "bad.iso"
            iso.write_bytes(b"not-a-sector")

            with self.assertRaises(SaturnMode1ImageError):
                write_single_track_mode1_bin_cue(
                    iso,
                    root / "disc.bin",
                    root / "disc.cue",
                )

    def test_refuses_to_overwrite_existing_bin_or_cue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iso = root / "source.iso"
            iso.write_bytes(bytes(2048))
            raw = root / "disc.bin"
            cue = root / "disc.cue"
            raw.write_bytes(b"preserve")

            with self.assertRaises(SaturnMode1ImageError):
                write_single_track_mode1_bin_cue(iso, raw, cue)

            self.assertEqual(raw.read_bytes(), b"preserve")
            self.assertFalse(cue.exists())


if __name__ == "__main__":
    unittest.main()
