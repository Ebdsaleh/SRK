from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    build_saturn_midi_68k_r24_song_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_fidelity import (
    build_saturn_midi_68k_r25_fidelity_profile,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


class SaturnMidi68KR25FidelityTests(unittest.TestCase):
    def test_reference_profile_combines_release_progress_and_calibration_contracts(self):
        source = build_saturn_midi_68k_r24_song_profile(_REFERENCE)
        profile = build_saturn_midi_68k_r25_fidelity_profile(source)
        self.assertEqual(len(profile.note_audit.spans), 140)
        self.assertEqual(profile.final_release_state.telemetry.release_completed_count, 138)
        self.assertEqual(profile.final_release_state.telemetry.release_cancelled_count, 2)
        self.assertEqual(profile.final_release_state.owned_count, 0)
        self.assertEqual(len(profile.progress_checkpoints), 5)
        self.assertEqual(profile.progress_checkpoints[0].permille, 0)
        self.assertEqual(profile.progress_checkpoints[-1].permille, 1000)
        self.assertEqual(profile.progress_checkpoints[-1].clock_text, "01:48.151/01:48.151 100%")
        self.assertEqual(len(profile.rr_calibration), 32)
        self.assertTrue(
            all(entry.measured_release_us is None for entry in profile.rr_calibration)
        )


if __name__ == "__main__":
    unittest.main()
