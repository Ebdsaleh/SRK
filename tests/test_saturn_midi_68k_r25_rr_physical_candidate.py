"""Regression contracts for the R25 RR physical calibration renderer."""

import unittest

import rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate as _r23
from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate import (
    derive_r24_physical_candidate_main,
    derive_r24_physical_candidate_menu,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_physical_candidate import (
    derive_r25_rr_calibration_candidate_main,
    derive_r25_rr_calibration_candidate_menu,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_source,
)
from tests.test_saturn_midi_68k_resident_audio_candidate_prepare import _synthetic_stream_main


class SaturnMidi68KR25RRPhysicalCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.header = render_srk_saturn_midi_68k_r25_rr_calibration_proof_header(
            release_rate=16
        )
        cls.source = render_srk_saturn_midi_68k_r25_rr_calibration_proof_source(
            release_rate=16
        )

    def test_renderer_locks_explicit_rr_a4_and_two_second_window(self):
        source = self.source
        self.assertIn("SRK_R25_CAL_RELEASE_RATE 16u", source)
        self.assertIn("SRK_R25_CAL_EXPECTED_EG2 0x3C10u", source)
        self.assertIn("SRK_R25_CAL_NOTE_ON_US 250000UL", source)
        self.assertIn("SRK_R25_CAL_NOTE_OFF_US 1250000UL", source)
        self.assertIn("SRK_R25_CAL_OBSERVATION_US 2000000UL", source)
        self.assertIn("SRK_R25_CAL_END_US 3250000UL", source)
        self.assertIn("{250000UL", source)
        self.assertIn("{1250000UL", source)

    def test_renderer_uses_accepted_r24_frt_and_restores_tcr(self):
        source = self.source
        self.assertIn("26874100UL", source)
        self.assertIn("28636400UL", source)
        self.assertIn("26687700UL", source)
        self.assertIn("28437700UL", source)
        self.assertIn("srk_saturn_midi_r24_frt_configure_div128", source)
        self.assertIn("state->original_tcr = SRK_R25_CAL_FRT_TCR", source)
        self.assertIn("SRK_R25_CAL_FRT_TCR = state->original_tcr", source)

    def test_renderer_observes_release_ledger_without_fake_envelope_readback(self):
        source = self.source
        self.assertIn("slot0_release_start_us != SRK_R25_CAL_NOTE_OFF_US", source)
        self.assertIn("slot0_release_deadline_us != SRK_R25_CAL_END_US", source)
        self.assertIn("voice_release_completed == 1u", source)
        self.assertIn("voice_releasing_count == 0u", source)
        self.assertNotIn("MSLC", source)
        self.assertNotIn("envelope_level", source)
        self.assertNotIn("envelope_phase", source)

    def test_header_exposes_operator_timing_and_release_telemetry(self):
        for marker in (
            "clock_source_hz",
            "clock_us",
            "release_elapsed_us",
            "release_rate",
            "voice_held_count",
            "voice_releasing_count",
            "voice_release_started",
            "voice_release_completed",
            "slot0_release_start_us",
            "slot0_release_deadline_us",
        ):
            self.assertIn(marker, self.header)

    def test_main_and_menu_derive_from_accepted_r24_shape(self):
        stream_main = _synthetic_stream_main()
        r23_main = _r23.derive_resident_audio_candidate_main(stream_main)
        r24_main = derive_r24_physical_candidate_main(r23_main)
        r25_main = derive_r25_rr_calibration_candidate_main(r24_main, release_rate=16)
        self.assertTrue(
            r25_main.startswith("#define SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE 1\n")
        )
        self.assertIn("MIDI / 68K R25 RR CAL", r25_main)
        self.assertIn("RR 16 A4 - off 1.25s - observe 2.00s", r25_main)
        self.assertIn("RR 16 probe done - production RR UNSET", r25_main)
        self.assertIn("telemetry.release_elapsed_us", r25_main)
        self.assertNotIn("#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1\n", r25_main)

        r23_menu = _r23.derive_resident_audio_candidate_menu(
            'x\n"MIDI 68K Stream Proof"\ny\n'
        )
        r24_menu = derive_r24_physical_candidate_menu(r23_menu)
        r25_menu = derive_r25_rr_calibration_candidate_menu(r24_menu)
        self.assertIn('"MIDI 68K R25 RR Cal"', r25_menu)
        self.assertNotIn('"MIDI 68K Song Proof"', r25_menu)


if __name__ == "__main__":
    unittest.main()
