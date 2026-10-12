"""Regression contracts for the R24 two-slot resident MIDI -> SCSP service."""

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_pitch import (
    build_saturn_midi_68k_r24_pitch_table,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END,
    SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS,
    SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_END,
    SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS,
    SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS,
    build_saturn_midi_68k_r24_mixer_table,
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
    render_srk_saturn_midi_68k_r24_resident_audio_service_header,
    render_srk_saturn_midi_68k_r24_resident_audio_service_source,
    render_srk_saturn_midi_68k_r24_voice_header,
    validate_saturn_midi_68k_r24_resident_audio_layout,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    build_srk_saturn_midi_68k_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    midi_velocity_to_scsp_mixer,
)


_ACCEPTED_R23_AUDIO_IMAGE_SHA256 = (
    "cb172de4e984dd50fcec195c310cb2945abb10bdaa561d31d52062b7e79038a1"
)


def _contains_words(haystack: tuple[int, ...], needle: tuple[int, ...]) -> bool:
    width = len(needle)
    return any(
        haystack[index : index + width] == needle
        for index in range(len(haystack) - width + 1)
    )


class SaturnMidi68KR24ResidentAudioServiceTests(unittest.TestCase):
    def test_r23_physical_image_remains_exact_before_and_after_r24_derivation(self):
        before = build_srk_saturn_midi_68k_resident_audio_service_image()
        self.assertEqual(before.sha256, _ACCEPTED_R23_AUDIO_IMAGE_SHA256)
        _ = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
        after = build_srk_saturn_midi_68k_resident_audio_service_image()
        self.assertEqual(after.sha256, _ACCEPTED_R23_AUDIO_IMAGE_SHA256)
        self.assertEqual(before, after)

    def test_r24_image_is_deterministic_distinct_and_bounded(self):
        first = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
        second = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
        r23 = build_srk_saturn_midi_68k_resident_audio_service_image()
        self.assertEqual(first, second)
        self.assertEqual(first.sha256, second.sha256)
        self.assertNotEqual(first.sha256, r23.sha256)
        self.assertEqual(SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS, 0x00004000)
        self.assertEqual(SATURN_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS, 0x0007FFF0)
        self.assertLessEqual(first.end_address, SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_END)
        self.assertLessEqual(first.end_address, 0x00008000)

    def test_r24_audio_data_layout_is_fresh_bounded_and_non_overlapping(self):
        validate_saturn_midi_68k_r24_resident_audio_layout()
        self.assertEqual(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 0x00002200)
        self.assertEqual(SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS, 0x00002300)
        self.assertEqual(SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS, 0x00002400)
        self.assertEqual(SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END, 0x00002500)
        self.assertLess(SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END, 0x00004000)

    def test_r24_tables_are_complete_and_use_calibrated_pitch(self):
        pitches = build_saturn_midi_68k_r24_pitch_table()
        mixers = build_saturn_midi_68k_r24_mixer_table()
        self.assertEqual(len(pitches), 128)
        self.assertEqual(len(mixers), 128)
        self.assertNotEqual(pitches[60], 0x0000)
        self.assertEqual(mixers[0], 0)
        self.assertEqual(mixers[100], midi_velocity_to_scsp_mixer(100))
        self.assertEqual(mixers[127], midi_velocity_to_scsp_mixer(127))

    def test_r24_image_contains_only_68k_scsp_window_not_sh2_alias(self):
        words = build_srk_saturn_midi_68k_r24_resident_audio_service_image().words
        self.assertTrue(_contains_words(words, (0x49F9, 0x0010, 0x0000)))
        self.assertTrue(_contains_words(words, (0x4BF9, 0x0010, 0x0400)))
        self.assertFalse(_contains_words(words, (0x25B0, 0x0000)))
        self.assertFalse(_contains_words(words, (0x25B0, 0x0400)))

    def test_r24_generated_contract_exposes_two_slots_and_inert_program_data(self):
        header = render_srk_saturn_midi_68k_r24_resident_audio_service_header()
        voice = render_srk_saturn_midi_68k_r24_voice_header()
        source = render_srk_saturn_midi_68k_r24_resident_audio_service_source()
        self.assertIn("R24_RESIDENT_AUDIO_PROGRAM_ADDRESS 0x00004000UL", header)
        self.assertIn("R24_RESIDENT_AUDIO_MAX_RECORDS 32u", header)
        self.assertIn("R24_VOICE_STATE_ADDRESS 0x00002300UL", voice)
        self.assertIn("R24_MIXER_TABLE_ADDRESS 0x00002400UL", voice)
        self.assertIn("R24_OWNED_SLOTS 2u", voice)
        self.assertIn(
            "const unsigned short srk_saturn_midi_68k_r24_resident_audio_service_program[]",
            source,
        )
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x25A00000", source)
        self.assertNotIn("volatile", source)
        self.assertNotIn("main(", source)


if __name__ == "__main__":
    unittest.main()
