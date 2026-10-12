"""Regression contracts for the R25 four-slot release-tail service."""

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_envelope import (
    SaturnMidi68KR25EnvelopeError,
    build_saturn_midi_68k_r25_envelope_plan,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_resident_audio_service import (
    SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END,
    SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS,
    SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END,
    SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_R25_SLOT_BASE_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD,
    SATURN_MIDI_68K_R25_SLOT_WORDS,
    SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS,
    build_srk_saturn_midi_68k_r25_resident_audio_service_image,
    render_srk_saturn_midi_68k_r25_resident_audio_service_header,
    render_srk_saturn_midi_68k_r25_resident_audio_service_source,
    render_srk_saturn_midi_68k_r25_voice_header,
    validate_saturn_midi_68k_r25_resident_audio_layout,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    build_srk_saturn_midi_68k_resident_audio_service_image,
)


_ACCEPTED_R23_SHA256 = "cb172de4e984dd50fcec195c310cb2945abb10bdaa561d31d52062b7e79038a1"
_ACCEPTED_R24_SHA256 = "e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e"


def _contains_words(haystack: tuple[int, ...], needle: tuple[int, ...]) -> bool:
    return any(
        haystack[index : index + len(needle)] == needle
        for index in range(len(haystack) - len(needle) + 1)
    )


class SaturnMidi68KR25ResidentAudioServiceTests(unittest.TestCase):
    def test_r23_and_r24_images_remain_exact_across_r25_derivation(self):
        before_r23 = build_srk_saturn_midi_68k_resident_audio_service_image()
        before_r24 = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
        _ = build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=18)
        after_r23 = build_srk_saturn_midi_68k_resident_audio_service_image()
        after_r24 = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
        self.assertEqual(before_r23.sha256, _ACCEPTED_R23_SHA256)
        self.assertEqual(before_r24.sha256, _ACCEPTED_R24_SHA256)
        self.assertEqual(before_r23, after_r23)
        self.assertEqual(before_r24, after_r24)

    def test_layout_owns_four_slots_below_fresh_program_envelope(self):
        validate_saturn_midi_68k_r25_resident_audio_layout()
        self.assertEqual(SATURN_MIDI_68K_R25_OWNED_SLOTS, 4)
        self.assertEqual(SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS, 0x2300)
        self.assertEqual(SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS, 0x2400)
        self.assertEqual(SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END, 0x2500)
        self.assertEqual(SATURN_MIDI_68K_R25_SLOT_BASE_WORD, 32)
        self.assertEqual(SATURN_MIDI_68K_R25_SLOT_WORDS, 12)
        self.assertEqual(SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD, 10)
        self.assertEqual(SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD, 11)
        self.assertLess(SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END, SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS)

    def test_every_rr_variant_is_deterministic_explicit_and_bounded(self):
        images = tuple(
            build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=rr)
            for rr in range(32)
        )
        self.assertEqual(len({image.sha256 for image in images}), 32)
        self.assertEqual(len({image.word_count for image in images}), 1)
        for rr, image in enumerate(images):
            plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=rr)
            self.assertEqual(image.release_rate, rr)
            self.assertEqual(image.eg1_word, plan.eg1_word)
            self.assertEqual(image.eg2_word, plan.eg2_word)
            self.assertLessEqual(image.end_address, SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END)
            self.assertGreater(image.end_address, 0x8000)
            self.assertEqual(
                image,
                build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=rr),
            )

    def test_rr_is_required_and_invalid_rr_fails_closed(self):
        with self.assertRaises(TypeError):
            build_srk_saturn_midi_68k_r25_resident_audio_service_image()  # type: ignore[call-arg]
        with self.assertRaisesRegex(SaturnMidi68KR25EnvelopeError, "RR"):
            build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=32)

    def test_image_contains_release_deadline_arithmetic_and_scsp_words(self):
        plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=18)
        words = build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=18
        ).words
        self.assertTrue(_contains_words(words, (0x49F9, 0x0010, 0x0000)))
        self.assertFalse(_contains_words(words, (0x25B0, 0x0000)))
        # ADDI.W #0xD4C0,D0 is the low-word part of +120000 us.
        self.assertTrue(_contains_words(words, (0x0640, SATURN_MIDI_68K_R25_TARGET_RELEASE_US & 0xFFFF)))
        self.assertIn(plan.eg1_word, words)
        self.assertIn(plan.eg2_word, words)

    def test_generated_contract_is_inert_and_names_release_policy(self):
        header = render_srk_saturn_midi_68k_r25_resident_audio_service_header(release_rate=18)
        voice = render_srk_saturn_midi_68k_r25_voice_header()
        source = render_srk_saturn_midi_68k_r25_resident_audio_service_source(release_rate=18)
        self.assertIn("R25_RELEASE_RATE 18u", header)
        self.assertIn("R25_EG1_WORD 0x001Fu", header)
        self.assertIn("R25_EG2_WORD 0x3C12u", header)
        self.assertIn("R25_TARGET_RELEASE_US 120000UL", header)
        self.assertIn("R25_OWNED_SLOTS 4u", voice)
        self.assertIn("R25_SLOT_WORDS 12u", voice)
        self.assertIn("srk_saturn_midi_68k_r25_resident_audio_service_program", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("volatile", source)
        self.assertNotIn("main(", source)


if __name__ == "__main__":
    unittest.main()
