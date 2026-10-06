"""Tests for SRK's read-only multi-track CUE logical-disc layer."""

import os
import tempfile
import unittest

from rikai_kotoba.core.cue_disc import (
    CueDisc,
    NonDataTrackError,
    parse_cue,
)


def _mode1_2352_sector(marker):
    sector = bytearray(2352)
    sector[15] = 0x01
    sector[16 : 16 + 2048] = bytes([marker]) * 2048
    return bytes(sector)


class CueDiscTests(unittest.TestCase):
    def _write(self, path, data):
        with open(path, "wb") as handle:
            handle.write(data)

    def _make_two_file_disc(self, temp_dir):
        data_path = os.path.join(temp_dir, "Track 1.bin")
        audio_path = os.path.join(temp_dir, "Track 2.bin")
        cue_path = os.path.join(temp_dir, "Game.cue")

        self._write(
            data_path,
            _mode1_2352_sector(0x11) + _mode1_2352_sector(0x22),
        )
        self._write(audio_path, bytes([0xA0]) * 2352 + bytes([0xB0]) * 2352)

        with open(cue_path, "w", encoding="utf-8") as handle:
            handle.write(
                'FILE "Track 1.bin" BINARY\n'
                '  TRACK 01 MODE1/2352\n'
                '    INDEX 01 00:00:00\n'
                'FILE "Track 2.bin" BINARY\n'
                '  TRACK 02 AUDIO\n'
                '    INDEX 01 00:00:00\n'
            )
        return cue_path, data_path, audio_path

    def test_parse_cue_preserves_track_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cue_path, _, _ = self._make_two_file_disc(temp_dir)
            tracks = parse_cue(cue_path)

            self.assertEqual(len(tracks), 2)
            self.assertEqual(tracks[0].number, 1)
            self.assertEqual(tracks[0].mode.name, "MODE1/2352")
            self.assertEqual(tracks[1].number, 2)
            self.assertEqual(tracks[1].mode.name, "AUDIO")

    def test_separate_track_files_form_contiguous_logical_lbas(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cue_path, _, audio_path = self._make_two_file_disc(temp_dir)
            disc = CueDisc(cue_path)

            self.assertEqual(disc.total_sectors, 4)
            location = disc.locate_lba(2)
            self.assertEqual(location.track_number, 2)
            self.assertEqual(
                os.path.normcase(location.file_path), os.path.normcase(audio_path)
            )
            self.assertEqual(location.file_sector, 0)
            self.assertEqual(disc.read_sector(2), bytes([0xA0]) * 2352)

    def test_mode1_user_data_is_extracted_without_loading_whole_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cue_path, _, _ = self._make_two_file_disc(temp_dir)
            disc = CueDisc(cue_path)

            self.assertEqual(disc.read_user_sector(0), bytes([0x11]) * 2048)
            self.assertEqual(disc.read_user_sector(1), bytes([0x22]) * 2048)

    def test_audio_track_is_reported_instead_of_silently_truncated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cue_path, _, _ = self._make_two_file_disc(temp_dir)
            disc = CueDisc(cue_path)

            with self.assertRaises(NonDataTrackError):
                disc.read_user_sector(2)

    def test_user_extent_can_cross_between_data_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = os.path.join(temp_dir, "A.bin")
            second = os.path.join(temp_dir, "B.bin")
            cue = os.path.join(temp_dir, "Data.cue")
            self._write(first, _mode1_2352_sector(0x31))
            self._write(second, _mode1_2352_sector(0x42))
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "A.bin" BINARY\n'
                    '  TRACK 01 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                    'FILE "B.bin" BINARY\n'
                    '  TRACK 02 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                )

            disc = CueDisc(cue)
            data = disc.read_user_extent(0, 2500)
            self.assertEqual(data[:2048], bytes([0x31]) * 2048)
            self.assertEqual(data[2048:], bytes([0x42]) * (2500 - 2048))

    def test_index_00_stored_pregap_is_mapped_to_second_track(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = os.path.join(temp_dir, "A.bin")
            second = os.path.join(temp_dir, "B.bin")
            cue = os.path.join(temp_dir, "Pregap.cue")
            self._write(first, _mode1_2352_sector(0x11))
            self._write(second, bytes(2352 * 151))
            with open(cue, "w", encoding="utf-8") as handle:
                handle.write(
                    'FILE "A.bin" BINARY\n'
                    '  TRACK 01 MODE1/2352\n'
                    '    INDEX 01 00:00:00\n'
                    'FILE "B.bin" BINARY\n'
                    '  TRACK 02 AUDIO\n'
                    '    INDEX 00 00:00:00\n'
                    '    INDEX 01 00:02:00\n'
                )

            disc = CueDisc(cue)
            location = disc.locate_lba(1)
            self.assertEqual(location.track_number, 2)
            self.assertEqual(location.file_sector, 0)


if __name__ == "__main__":
    unittest.main()
