"""Tests for the non-interactive Mjolnir helper functions."""

import os
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.tools.mjolnir import (
    _next_numbered_backup_path,
    _write_with_conflict_resolution,
    discover_disc_candidates,
    open_disc,
)


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


def _writer_for(payload):
    def writer(path, overwrite):
        mode = "w" if overwrite else "x"
        with open(path, mode, encoding="utf-8") as handle:
            handle.write(payload)
        return os.path.abspath(path)

    return writer


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

    def test_numbered_backup_uses_first_available_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            for name in (
                "SAMPLE.DAT.hex",
                "SAMPLE.DAT(1).hex",
                "SAMPLE.DAT(2).hex",
            ):
                with open(
                    os.path.join(temp_dir, name),
                    "w",
                    encoding="utf-8",
                ) as handle:
                    handle.write(name)

            self.assertEqual(
                _next_numbered_backup_path(output),
                os.path.join(temp_dir, "SAMPLE.DAT(3).hex"),
            )

    def test_conflict_cancel_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("old")

            result = _write_with_conflict_resolution(
                output,
                _writer_for("new"),
                input_func=lambda _prompt: "1",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "cancelled")
            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

    def test_conflict_empty_input_defaults_to_cancel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("old")

            result = _write_with_conflict_resolution(
                output,
                _writer_for("new"),
                input_func=lambda _prompt: "",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "cancelled")
            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

    def test_conflict_auto_rename_preserves_old_and_writes_new(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            existing_backup = os.path.join(temp_dir, "SAMPLE.DAT(1).hex")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("old")
            with open(existing_backup, "w", encoding="utf-8") as handle:
                handle.write("older")

            result = _write_with_conflict_resolution(
                output,
                _writer_for("new"),
                input_func=lambda _prompt: "2",
                print_func=lambda _message: None,
            )

            expected_backup = os.path.join(temp_dir, "SAMPLE.DAT(2).hex")
            self.assertEqual(result.action, "renamed_existing")
            self.assertEqual(result.backup_path, expected_backup)
            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "new")
            with open(existing_backup, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "older")
            with open(expected_backup, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

    def test_conflict_overwrite_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("old")

            result = _write_with_conflict_resolution(
                output,
                _writer_for("new"),
                input_func=lambda _prompt: "3",
                print_func=lambda _message: None,
            )

            self.assertEqual(result.action, "overwritten")
            self.assertIsNone(result.backup_path)
            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "new")

    def test_auto_rename_rolls_back_if_final_placement_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = os.path.join(temp_dir, "SAMPLE.DAT.hex")
            with open(output, "w", encoding="utf-8") as handle:
                handle.write("old")

            with patch(
                "rikai_kotoba.tools.mjolnir.os.replace",
                side_effect=OSError("simulated placement failure"),
            ):
                with self.assertRaises(OSError):
                    _write_with_conflict_resolution(
                        output,
                        _writer_for("new"),
                        input_func=lambda _prompt: "2",
                        print_func=lambda _message: None,
                    )

            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")
            self.assertFalse(
                os.path.exists(os.path.join(temp_dir, "SAMPLE.DAT(1).hex"))
            )


if __name__ == "__main__":
    unittest.main()
