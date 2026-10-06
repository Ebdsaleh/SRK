"""Tests for generic disc-source discovery and opening."""

import os
import tempfile
import unittest

from rikai_kotoba.core.cue_disc import CueDisc
from rikai_kotoba.core.disc_image import DiscImage
from rikai_kotoba.core.disc_source import (
    UnsupportedDiscSourceError,
    discover_disc_candidates,
    open_disc_source,
)


SECTOR = 2048


def _make_iso2048(path):
    image = bytearray(SECTOR * 24)
    pvd = bytearray(SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01

    root = bytearray(34)
    root[0] = 34
    root[2:6] = (20).to_bytes(4, "little")
    root[6:10] = (20).to_bytes(4, "big")
    root[10:14] = SECTOR.to_bytes(4, "little")
    root[14:18] = SECTOR.to_bytes(4, "big")
    root[25] = 0x02
    root[28:30] = (1).to_bytes(2, "little")
    root[30:32] = (1).to_bytes(2, "big")
    root[32] = 1
    root[33] = 0
    pvd[156:190] = root
    image[16 * SECTOR : 17 * SECTOR] = pvd

    with open(path, "wb") as handle:
        handle.write(image)


class DiscSourceTests(unittest.TestCase):
    def test_open_standalone_iso_uses_disc_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.iso")
            _make_iso2048(path)

            source = open_disc_source(path)

            self.assertIsInstance(source, DiscImage)
            self.assertEqual(source.geometry.name, "MODE1/2048")

    def test_open_cue_uses_cue_disc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            track = os.path.join(temp_dir, "Track 1.bin")
            with open(track, "wb") as handle:
                handle.write(b"\0" * 2352)

            cue = os.path.join(temp_dir, "Game.cue")
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "Track 1.bin" BINARY\n'
                    '  TRACK 01 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                )

            source = open_disc_source(cue)

            self.assertIsInstance(source, CueDisc)
            self.assertEqual(len(source.tracks), 1)

    def test_discovery_prefers_cue_over_referenced_track_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            for name in ("Track 1.bin", "Track 2.bin", "Standalone.iso"):
                with open(os.path.join(temp_dir, name), "wb") as handle:
                    handle.write(b"\0" * 2352)

            cue = os.path.join(temp_dir, "Game.cue")
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "Track 1.bin" BINARY\n'
                    '  TRACK 01 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                    'FILE "Track 2.bin" BINARY\n'
                    '  TRACK 02 AUDIO\n'
                    '    INDEX 01 00:00:00\n'
                )

            candidates = discover_disc_candidates(temp_dir)

            self.assertEqual(
                [os.path.basename(path) for path in candidates],
                ["Game.cue", "Standalone.iso"],
            )

    def test_unsupported_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "not-a-disc.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not a disc")

            with self.assertRaises(UnsupportedDiscSourceError):
                open_disc_source(path)


if __name__ == "__main__":
    unittest.main()
