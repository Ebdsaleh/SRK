"""Tests for the non-interactive Mjolnir helper functions."""

import os
import tempfile
import unittest

from rikai_kotoba.tools.mjolnir import discover_disc_candidates, open_disc


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


def _make_iso2048(path):
    sectors = 40
    image = bytearray(SECTOR * sectors)

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


class MjolnirTests(unittest.TestCase):
    def test_disc_discovery_prefers_cue_over_referenced_tracks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            track1 = os.path.join(temp_dir, "Game Track 1.bin")
            track2 = os.path.join(temp_dir, "Game Track 2.bin")
            standalone = os.path.join(temp_dir, "Other.iso")
            for path in (track1, track2, standalone):
                with open(path, "wb") as handle:
                    handle.write(b"\0" * 2352)

            cue = os.path.join(temp_dir, "Game.cue")
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "Game Track 1.bin" BINARY\n'
                    '  TRACK 01 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                    'FILE "Game Track 2.bin" BINARY\n'
                    '  TRACK 02 AUDIO\n'
                    '    INDEX 01 00:00:00\n'
                )

            candidates = discover_disc_candidates(temp_dir)
            self.assertEqual(
                [os.path.basename(path) for path in candidates],
                ["Game.cue", "Other.iso"],
            )

    def test_open_disc_reads_standalone_iso_without_loading_it_wholesale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            iso = os.path.join(temp_dir, "sample.iso")
            _make_iso2048(iso)

            session = open_disc(iso)

            self.assertEqual(len(session.entries), 1)
            self.assertEqual(session.entries[0][0], "/HELLO.TXT")
            self.assertEqual(session.reader.read_file("/HELLO.TXT"), b"hello")
            self.assertEqual(session.base_name, "sample")


if __name__ == "__main__":
    unittest.main()
