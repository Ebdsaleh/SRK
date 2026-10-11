"""Regression contracts for the R23 resident MIDI -> SCSP service."""

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    SATURN_MIDI_68K_R23_PROOF_MIXER,
    SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END,
    SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS,
    build_srk_saturn_midi_68k_resident_audio_service_image,
    render_srk_saturn_midi_68k_resident_audio_service_header,
    render_srk_saturn_midi_68k_resident_audio_service_source,
    render_srk_saturn_midi_68k_resident_audio_voice_header,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_R23_HOLD_US,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
    build_srk_saturn_midi_68k_r23_first_note_snapshot,
    midi_velocity_to_scsp_mixer,
)


_ACCEPTED_R22A_STREAM_IMAGE_SHA256 = (
    "0d64b50b17dcae9318a7c6850ef2d46da84923ccfe0fa9f2611f0287ec59be02"
)


def _contains_words(haystack: tuple[int, ...], needle: tuple[int, ...]) -> bool:
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


class SaturnMidi68KResidentAudioServiceTests(unittest.TestCase):
    def test_r22a_stream_image_remains_exact_immutable_anchor(self):
        image = build_srk_saturn_midi_68k_resident_stream_service_image()
        self.assertEqual(image.sha256, _ACCEPTED_R22A_STREAM_IMAGE_SHA256)
        self.assertEqual(image.word_count, 5123)
        self.assertEqual(image.byte_size, 10246)
        self.assertEqual(image.end_address, 0x00006806)

    def test_r23_image_is_deterministic_distinct_and_bounded(self):
        first = build_srk_saturn_midi_68k_resident_audio_service_image()
        second = build_srk_saturn_midi_68k_resident_audio_service_image()
        base = build_srk_saturn_midi_68k_resident_stream_service_image()
        self.assertEqual(first, second)
        self.assertEqual(first.sha256, second.sha256)
        self.assertNotEqual(first.sha256, base.sha256)
        self.assertGreater(first.word_count, base.word_count)
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS, 0x00004000)
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS, 0x0007FFF0)
        self.assertLessEqual(first.end_address, SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END)
        self.assertLessEqual(first.end_address, 0x00008000)

    def test_r23_image_contains_only_reviewed_68k_scsp_windows(self):
        words = build_srk_saturn_midi_68k_resident_audio_service_image().words
        # LEA 0x00100000.L,A4 and LEA 0x00100400.L,A5.
        self.assertTrue(_contains_words(words, (0x49F9, 0x0010, 0x0000)))
        self.assertTrue(_contains_words(words, (0x4BF9, 0x0010, 0x0400)))
        # The 68K image must not embed the SH-2's 0x25Bxxxxx SCSP mapping.
        self.assertFalse(_contains_words(words, (0x25B0, 0x0000)))
        self.assertFalse(_contains_words(words, (0x25B0, 0x0400)))

    def test_r23_first_note_model_matches_resident_proof_constants(self):
        snapshot = build_srk_saturn_midi_68k_r23_first_note_snapshot()
        on = snapshot.after_note_on.owned_slot
        off = snapshot.after_note_off.owned_slot
        self.assertEqual(SATURN_MIDI_68K_R23_HOLD_US, 1_000_000)
        self.assertEqual(SATURN_MIDI_68K_R23_PROOF_MIXER, midi_velocity_to_scsp_mixer(100))
        self.assertEqual(SATURN_MIDI_68K_R23_PROOF_MIXER, 0xC000)
        self.assertEqual(on.pitch, 0x0000)
        self.assertEqual(on.mixer, 0xC000)
        self.assertEqual(
            on.control,
            SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
        )
        self.assertFalse(off.active)
        self.assertEqual(off.mixer, 0)

    def test_r23_generated_headers_expose_bounded_contract(self):
        resident = render_srk_saturn_midi_68k_resident_audio_service_header()
        voice = render_srk_saturn_midi_68k_resident_audio_voice_header()
        self.assertIn("SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS 0x00004000UL", resident)
        self.assertIn("SRK_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS 32u", resident)
        self.assertIn("SRK_MIDI_68K_SCSP_REGISTER_BASE 0x00100000UL", voice)
        self.assertIn("SRK_MIDI_68K_VOICE_STATE_ADDRESS 0x00002100UL", voice)
        self.assertIn("SRK_MIDI_68K_R23_OWNED_SLOTS 1u", voice)
        self.assertIn("SRK_MIDI_68K_R23_HOLD_US 1000000UL", voice)

    def test_r23_generated_source_is_inert_constant_data(self):
        source = render_srk_saturn_midi_68k_resident_audio_service_source()
        self.assertIn("const unsigned short srk_saturn_midi_68k_resident_audio_service_program[]", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x25A00000", source)
        self.assertNotIn("volatile", source)
        self.assertNotIn("main(", source)

    def test_voice_telemetry_is_below_resident_program_and_outside_r22a_state(self):
        self.assertEqual(SATURN_MIDI_68K_VOICE_STATE_ADDRESS, 0x00002100)
        self.assertGreaterEqual(SATURN_MIDI_68K_VOICE_STATE_ADDRESS, 0x00002000)
        self.assertLess(SATURN_MIDI_68K_VOICE_STATE_ADDRESS, SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS)


if __name__ == "__main__":
    unittest.main()
