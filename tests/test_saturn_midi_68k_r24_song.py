from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
    SATURN_MIDI_68K_R24_REFERENCE_DURATION_US,
    SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_MAX,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_MIN,
    SATURN_MIDI_68K_R24_REFERENCE_OVERLAP_TIMES_US,
    SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
    SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
    SaturnMidi68KR24SongError,
    batch_saturn_midi_r24_program,
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KR24SongTests(unittest.TestCase):
    @staticmethod
    def _asset() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "midi"
            / "cc0"
            / "melody-town-theme"
            / "Melody Town Theme.mid"
        )

    def test_reference_real_smf_matches_reviewed_contract(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        validate_saturn_midi_68k_r24_reference_song(profile)
        self.assertEqual(profile.record_count, SATURN_MIDI_68K_R24_REFERENCE_RECORDS)
        self.assertEqual(profile.duration_us, SATURN_MIDI_68K_R24_REFERENCE_DURATION_US)
        self.assertEqual(profile.note_min, SATURN_MIDI_68K_R24_REFERENCE_NOTE_MIN)
        self.assertEqual(profile.note_max, SATURN_MIDI_68K_R24_REFERENCE_NOTE_MAX)
        self.assertEqual(profile.peak_polyphony, SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY)
        self.assertEqual(profile.overlap_times_us, SATURN_MIDI_68K_R24_REFERENCE_OVERLAP_TIMES_US)

    def test_reference_uses_ten_strict_queue_batches(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        self.assertEqual(len(profile.batches), SATURN_MIDI_68K_R24_REFERENCE_BATCHES)
        self.assertEqual(tuple(batch.record_count for batch in profile.batches), (32,) * 9 + (22,))
        self.assertEqual(profile.batches[-1].record_count, SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS)
        self.assertEqual(tuple(batch.sequence for batch in profile.batches), tuple(range(1, 11)))
        self.assertEqual(profile.batches[0].first_record_index, 0)
        self.assertEqual(profile.batches[-1].first_record_index, 288)

    def test_reference_channel_event_counts_are_exact(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        counts = dict(profile.opcode_counts)
        self.assertEqual(counts[SaturnMidiOpcode.NOTE_ON], 140)
        self.assertEqual(counts[SaturnMidiOpcode.NOTE_OFF], 140)
        self.assertEqual(counts[SaturnMidiOpcode.CONTROL_CHANGE], 23)
        self.assertEqual(counts[SaturnMidiOpcode.PROGRAM_CHANGE], 3)
        self.assertEqual(counts[SaturnMidiOpcode.PITCH_BEND], 4)
        self.assertNotIn(SaturnMidiOpcode.POLY_AFTERTOUCH, counts)
        self.assertNotIn(SaturnMidiOpcode.CHANNEL_PRESSURE, counts)

    def test_reference_batch_time_boundaries_remain_chronological(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        previous = -1
        for batch in profile.batches:
            self.assertLessEqual(batch.first_time_us, batch.last_time_us)
            self.assertGreaterEqual(batch.first_time_us, previous)
            previous = batch.last_time_us
        self.assertEqual(profile.batches[-1].last_time_us, profile.duration_us)

    def test_batcher_rejects_invalid_capacity(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        with self.assertRaises(SaturnMidi68KR24SongError):
            batch_saturn_midi_r24_program(profile.program, capacity=0)
        with self.assertRaises(SaturnMidi68KR24SongError):
            batch_saturn_midi_r24_program(profile.program, capacity=33)


if __name__ == "__main__":
    unittest.main()
