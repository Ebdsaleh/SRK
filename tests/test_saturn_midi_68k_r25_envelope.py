import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r25_envelope import (
    SATURN_MIDI_68K_R25_ATTACK_RATE,
    SATURN_MIDI_68K_R25_DECAY1_RATE,
    SATURN_MIDI_68K_R25_DECAY2_RATE,
    SATURN_MIDI_68K_R25_DECAY_LEVEL,
    SATURN_MIDI_68K_R25_KEY_RATE_SCALING_OFF,
    SaturnMidi68KR25EnvelopeError,
    build_saturn_midi_68k_r25_envelope_plan,
    pack_saturn_midi_68k_r25_eg1,
    pack_saturn_midi_68k_r25_eg2,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
)


class SaturnMidi68KR25EnvelopeTests(unittest.TestCase):
    def test_eg1_packing_matches_scsp_bit_layout(self):
        self.assertEqual(
            pack_saturn_midi_68k_r25_eg1(d2r=0x1F, d1r=0x1F, eg_hold=True, ar=0x1F),
            0xFFFF,
        )
        self.assertEqual(
            pack_saturn_midi_68k_r25_eg1(d2r=0, d1r=0, eg_hold=False, ar=0x1F),
            0x001F,
        )

    def test_eg2_packing_matches_scsp_bit_layout(self):
        self.assertEqual(
            pack_saturn_midi_68k_r25_eg2(
                loop_start_link=False,
                krs=0x0F,
                decay_level=0,
                release_rate=0x12,
            ),
            0x3C12,
        )
        self.assertEqual(
            pack_saturn_midi_68k_r25_eg2(
                loop_start_link=True,
                krs=0x0F,
                decay_level=0x1F,
                release_rate=0x1F,
            ),
            0x7FFF,
        )

    def test_candidate_plan_requires_explicit_release_rate_and_no_hard_mute(self):
        plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=0x12)
        self.assertEqual(plan.attack_rate, SATURN_MIDI_68K_R25_ATTACK_RATE)
        self.assertEqual(plan.decay1_rate, SATURN_MIDI_68K_R25_DECAY1_RATE)
        self.assertEqual(plan.decay2_rate, SATURN_MIDI_68K_R25_DECAY2_RATE)
        self.assertEqual(plan.decay_level, SATURN_MIDI_68K_R25_DECAY_LEVEL)
        self.assertEqual(plan.key_rate_scaling, SATURN_MIDI_68K_R25_KEY_RATE_SCALING_OFF)
        self.assertEqual(plan.target_release_us, SATURN_MIDI_68K_R25_TARGET_RELEASE_US)
        self.assertEqual(plan.owned_slots, SATURN_MIDI_68K_R25_OWNED_SLOTS)
        self.assertFalse(plan.hard_mixer_zero_on_note_off)
        self.assertEqual(plan.eg1_word, 0x001F)
        self.assertEqual(plan.eg2_word, 0x3C12)

    def test_release_rate_outside_scsp_field_is_rejected(self):
        with self.assertRaisesRegex(SaturnMidi68KR25EnvelopeError, "RR"):
            build_saturn_midi_68k_r25_envelope_plan(release_rate=0x20)

    def test_target_release_must_be_positive(self):
        with self.assertRaisesRegex(SaturnMidi68KR25EnvelopeError, "positive"):
            build_saturn_midi_68k_r25_envelope_plan(release_rate=1, target_release_us=0)


if __name__ == "__main__":
    unittest.main()
