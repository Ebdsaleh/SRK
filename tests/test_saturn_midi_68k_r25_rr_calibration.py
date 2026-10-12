import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration import (
    SaturnMidi68KR25RRCalibrationError,
    build_saturn_midi_68k_r25_rr_calibration_matrix,
    select_saturn_midi_68k_r25_rr,
)


class SaturnMidi68KR25RRCalibrationTests(unittest.TestCase):
    def test_matrix_covers_every_rr_field_value_and_register_word(self):
        entries = build_saturn_midi_68k_r25_rr_calibration_matrix()
        self.assertEqual(len(entries), 32)
        self.assertEqual(tuple(entry.release_rate for entry in entries), tuple(range(32)))
        self.assertEqual(entries[0].eg1_word, 0x001F)
        self.assertEqual(entries[0].eg2_word, 0x3C00)
        self.assertEqual(entries[31].eg2_word, 0x3C1F)
        self.assertTrue(all(entry.measured_release_us is None for entry in entries))

    def test_policy_selection_refuses_to_guess_without_physical_measurement(self):
        entries = build_saturn_midi_68k_r25_rr_calibration_matrix()
        with self.assertRaisesRegex(SaturnMidi68KR25RRCalibrationError, "measurements"):
            select_saturn_midi_68k_r25_rr(entries)

    def test_nearest_measured_release_is_selected_with_stable_tie_break(self):
        entries = build_saturn_midi_68k_r25_rr_calibration_matrix(
            {10: 110_000, 11: 130_000, 12: 121_000}
        )
        selected = select_saturn_midi_68k_r25_rr(entries, target_release_us=120_000)
        self.assertEqual(selected.release_rate, 12)
        self.assertEqual(selected.measured_release_us, 121_000)
        self.assertEqual(selected.absolute_error_us, 1_000)

    def test_invalid_measurements_are_rejected(self):
        with self.assertRaises(SaturnMidi68KR25RRCalibrationError):
            build_saturn_midi_68k_r25_rr_calibration_matrix({32: 100})
        with self.assertRaises(SaturnMidi68KR25RRCalibrationError):
            build_saturn_midi_68k_r25_rr_calibration_matrix({1: 0})


if __name__ == "__main__":
    unittest.main()
