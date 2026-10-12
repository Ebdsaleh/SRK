import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_pitch import (
    SATURN_MIDI_68K_R24_BASE_FREQUENCY_HZ,
    SaturnMidi68KR24PitchError,
    build_saturn_midi_68k_r24_pitch_point,
    build_saturn_midi_68k_r24_pitch_table,
    decode_scsp_pitch_multiplier,
    encode_scsp_pitch_multiplier,
    midi_note_frequency_hz,
    validate_saturn_midi_68k_r24_pitch_table,
)


class SaturnMidi68KR24PitchTests(unittest.TestCase):
    def test_full_table_is_musically_calibrated_below_one_cent(self):
        validate_saturn_midi_68k_r24_pitch_table()
        table = build_saturn_midi_68k_r24_pitch_table()
        self.assertEqual(len(table), 128)
        worst = max(abs(build_saturn_midi_68k_r24_pitch_point(note).error_cents) for note in range(128))
        self.assertLess(worst, 1.0)

    def test_a4_maps_the_proven_waveform_back_to_440_hz(self):
        point = build_saturn_midi_68k_r24_pitch_point(69)
        self.assertAlmostEqual(midi_note_frequency_hz(69), 440.0, places=9)
        self.assertLess(abs(point.actual_hz - 440.0), 0.25)
        self.assertNotEqual(point.pitch_word, 0)
        self.assertAlmostEqual(
            point.actual_hz,
            SATURN_MIDI_68K_R24_BASE_FREQUENCY_HZ * decode_scsp_pitch_multiplier(point.pitch_word),
            places=9,
        )

    def test_reference_song_note_range_uses_calibrated_distinct_pitches(self):
        points = [build_saturn_midi_68k_r24_pitch_point(note) for note in range(71, 87)]
        self.assertEqual(len({point.pitch_word for point in points}), 16)
        self.assertTrue(all(abs(point.error_cents) < 1.0 for point in points))
        self.assertTrue(all(a.actual_hz < b.actual_hz for a, b in zip(points, points[1:])))

    def test_multiplier_codec_handles_below_and_above_unity(self):
        for ratio in (0.25, 0.5, 440.0 / 441.0, 1.0, 1.5, 2.0, 4.0):
            pitch = encode_scsp_pitch_multiplier(ratio)
            actual = decode_scsp_pitch_multiplier(pitch)
            self.assertGreater(actual, 0.0)
            self.assertLess(abs(1200.0 * __import__("math").log2(actual / ratio)), 1.0)

    def test_rejects_invalid_note_or_multiplier(self):
        with self.assertRaises(SaturnMidi68KR24PitchError):
            midi_note_frequency_hz(-1)
        with self.assertRaises(SaturnMidi68KR24PitchError):
            midi_note_frequency_hz(128)
        with self.assertRaises(SaturnMidi68KR24PitchError):
            encode_scsp_pitch_multiplier(0.0)


if __name__ == "__main__":
    unittest.main()
