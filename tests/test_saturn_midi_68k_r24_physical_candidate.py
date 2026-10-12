"""Regression contracts for the R24 real-SMF physical proof renderer."""

from pathlib import Path
import unittest

import rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate as _r23
from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate import (
    SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
    build_srk_saturn_midi_68k_r24_expected_midi_words,
    derive_r24_physical_candidate_main,
    derive_r24_physical_candidate_menu,
    render_srk_saturn_midi_68k_r24_physical_proof_header,
    render_srk_saturn_midi_68k_r24_physical_proof_source,
    select_saturn_midi_68k_r24_source_hz,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    build_saturn_midi_68k_r24_song_profile,
)
from tests.test_saturn_midi_68k_resident_audio_candidate_prepare import (
    _synthetic_stream_main,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


class SaturnMidi68KR24PhysicalCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = build_saturn_midi_68k_r24_song_profile(_REFERENCE)
        cls.source = render_srk_saturn_midi_68k_r24_physical_proof_source(cls.profile)

    def test_clock_selector_covers_all_documented_saturn_groups(self):
        self.assertEqual(
            select_saturn_midi_68k_r24_source_hz(pal=False, group_b=False),
            SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
        )
        self.assertEqual(
            select_saturn_midi_68k_r24_source_hz(pal=False, group_b=True),
            SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
        )
        self.assertEqual(
            select_saturn_midi_68k_r24_source_hz(pal=True, group_b=False),
            SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
        )
        self.assertEqual(
            select_saturn_midi_68k_r24_source_hz(pal=True, group_b=True),
            SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
        )

    def test_renderer_uses_runtime_vdp2_clock_selection_and_restores_frt(self):
        source = self.source
        self.assertIn("0x25F80000UL", source)
        self.assertIn("0x25F80004UL", source)
        self.assertIn("tvstat & 0x0001u", source)
        self.assertIn("tvmd & 0x0001u", source)
        self.assertIn("26874100UL", source)
        self.assertIn("28636400UL", source)
        self.assertIn("26687700UL", source)
        self.assertIn("28437700UL", source)
        self.assertIn("state->original_tcr = SRK_R24_PROOF_FRT_TCR", source)
        self.assertIn("SRK_R24_PROOF_FRT_TCR = state->original_tcr", source)
        self.assertIn("srk_saturn_midi_r24_frt_configure_div128", source)
        self.assertIn("srk_r24_restore_frt(state);", source)

    def test_renderer_locks_complete_song_voice_and_refill_contract(self):
        source = self.source
        self.assertIn("state->telemetry.read_sequence != 10u", source)
        self.assertIn("state->telemetry.read_index != 22u", source)
        self.assertIn("state->telemetry.batch_count != 10u", source)
        self.assertIn("state->telemetry.total_processed != 310u", source)
        self.assertIn("state->telemetry.voice_key_on_count != 140u", source)
        self.assertIn("state->telemetry.voice_key_off_count != 140u", source)
        self.assertIn("state->telemetry.voice_busy_count != 0u", source)
        self.assertIn("state->telemetry.voice_active_count != 0u", source)
        self.assertIn("state->telemetry.voice_peak_active != 2u", source)
        self.assertIn("state->telemetry.polyphony_seen != 1u", source)
        self.assertIn("state->telemetry.player_sequence != 10u", source)
        self.assertIn("state->telemetry.player_complete != 1u", source)

    def test_renderer_verifies_the_full_1408_word_midi_state(self):
        summaries, controllers, active = build_srk_saturn_midi_68k_r24_expected_midi_words(
            self.profile
        )
        self.assertEqual(len(summaries), 256)
        self.assertEqual(len(controllers), 1024)
        self.assertEqual(len(active), 128)
        self.assertIn("srk_r24_expected_summary, 256u", self.source)
        self.assertIn("srk_r24_expected_controllers, 1024u", self.source)
        self.assertIn("srk_r24_expected_active, 128u", self.source)

    def test_candidate_main_and_menu_are_fresh_derivations_from_r23(self):
        stream_main = _synthetic_stream_main()
        r23_main = _r23.derive_resident_audio_candidate_main(stream_main)
        r24_main = derive_r24_physical_candidate_main(r23_main)
        self.assertTrue(r24_main.startswith("#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1\n"))
        self.assertIn("MIDI / 68K REAL SONG", r24_main)
        self.assertIn("310 events - FRT clock - two SCSP voices", r24_main)
        self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u", r24_main)
        self.assertIn("telemetry.voice_peak_active", r24_main)
        self.assertNotIn("#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1\n", r24_main)

        r23_menu = _r23.derive_resident_audio_candidate_menu(
            'x\n"MIDI 68K Stream Proof"\ny\n'
        )
        r24_menu = derive_r24_physical_candidate_menu(r23_menu)
        self.assertIn('"MIDI 68K Song Proof"', r24_menu)
        self.assertNotIn('"MIDI 68K Audio Proof"', r24_menu)

    def test_header_exposes_observable_physical_telemetry(self):
        header = render_srk_saturn_midi_68k_r24_physical_proof_header()
        for marker in (
            "clock_source_hz",
            "clock_us",
            "voice_key_on_count",
            "voice_key_off_count",
            "voice_busy_count",
            "voice_active_count",
            "voice_peak_active",
            "polyphony_seen",
            "state_verify_status",
        ):
            self.assertIn(marker, header)


if __name__ == "__main__":
    unittest.main()
