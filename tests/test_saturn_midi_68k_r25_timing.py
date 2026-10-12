import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r25_timing import (
    SaturnMidi68KR25TimingError,
    SaturnMidi68KR25TimingObservation,
    audit_saturn_midi_68k_r25_timing,
)


class SaturnMidi68KR25TimingTests(unittest.TestCase):
    def test_signed_early_late_and_exact_timing_are_reported(self):
        audit = audit_saturn_midi_68k_r25_timing(
            (
                SaturnMidi68KR25TimingObservation(0, 1000, 900),
                SaturnMidi68KR25TimingObservation(1, 2000, 2000),
                SaturnMidi68KR25TimingObservation(2, 3000, 3250),
            ),
            tolerance_us=200,
        )
        self.assertEqual(audit.observation_count, 3)
        self.assertEqual(audit.early_count, 1)
        self.assertEqual(audit.exact_count, 1)
        self.assertEqual(audit.late_count, 1)
        self.assertEqual(audit.maximum_early_us, 100)
        self.assertEqual(audit.maximum_late_us, 250)
        self.assertEqual(audit.maximum_absolute_error_us, 250)
        self.assertEqual(audit.violation_count, 1)

    def test_empty_audit_is_well_defined(self):
        audit = audit_saturn_midi_68k_r25_timing((), tolerance_us=0)
        self.assertEqual(audit.observation_count, 0)
        self.assertEqual(audit.maximum_absolute_error_us, 0)
        self.assertEqual(audit.violation_count, 0)

    def test_duplicate_or_out_of_order_indices_are_rejected(self):
        observations = (
            SaturnMidi68KR25TimingObservation(1, 100, 100),
            SaturnMidi68KR25TimingObservation(1, 200, 200),
        )
        with self.assertRaisesRegex(SaturnMidi68KR25TimingError, "strictly increasing"):
            audit_saturn_midi_68k_r25_timing(observations, tolerance_us=0)

    def test_negative_tolerance_is_rejected(self):
        with self.assertRaisesRegex(SaturnMidi68KR25TimingError, "non-negative"):
            audit_saturn_midi_68k_r25_timing((), tolerance_us=-1)


if __name__ == "__main__":
    unittest.main()
