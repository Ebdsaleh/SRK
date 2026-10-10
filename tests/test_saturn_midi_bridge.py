"""Regression tests for the pre-hardware Saturn MIDI bridge contract."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_MAILBOX_BYTES,
    SATURN_MIDI_MAILBOX_WORD_LAST_ERROR,
    SATURN_MIDI_MAILBOX_WORD_RESERVED,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_BYTES,
    SATURN_MIDI_QUEUE_CAPACITY,
    SATURN_MIDI_TONE_BANK_ADDRESS,
    SATURN_MIDI_TONE_BANK_BYTES,
    SATURN_MIDI_TONE_COUNT,
    SATURN_MIDI_TONE_SAMPLES,
    SATURN_SOUND_RAM_BYTES,
    build_srk_saturn_midi_bridge_assets,
    build_srk_saturn_midi_tone_bank,
    validate_srk_saturn_midi_layout,
)


class SaturnMidiBridgeTests(unittest.TestCase):
    def test_layout_is_bounded_and_non_overlapping(self):
        validate_srk_saturn_midi_layout()

        mailbox_end = SATURN_MIDI_MAILBOX_ADDRESS + SATURN_MIDI_MAILBOX_BYTES
        queue_end = SATURN_MIDI_QUEUE_ADDRESS + SATURN_MIDI_QUEUE_BYTES
        tone_end = SATURN_MIDI_TONE_BANK_ADDRESS + SATURN_MIDI_TONE_BANK_BYTES

        self.assertLessEqual(mailbox_end, SATURN_MIDI_QUEUE_ADDRESS)
        self.assertLessEqual(queue_end, SATURN_MIDI_TONE_BANK_ADDRESS)
        self.assertLessEqual(tone_end, SATURN_SOUND_RAM_BYTES)
        self.assertEqual(SATURN_MIDI_QUEUE_CAPACITY, 32)

    def test_mailbox_word_contract_fits_reserved_mailbox(self):
        self.assertEqual(SATURN_MIDI_MAILBOX_WORD_LAST_ERROR, 10)
        self.assertEqual(SATURN_MIDI_MAILBOX_WORD_RESERVED, 11)
        self.assertLess((SATURN_MIDI_MAILBOX_WORD_RESERVED + 1) * 2, SATURN_MIDI_MAILBOX_BYTES)

    def test_tone_bank_is_three_deterministic_pcm16_waveforms(self):
        bank = build_srk_saturn_midi_tone_bank()
        self.assertEqual(len(bank), SATURN_MIDI_TONE_COUNT)
        self.assertTrue(all(len(waveform) == SATURN_MIDI_TONE_SAMPLES for waveform in bank))

        square, triangle, saw = bank
        self.assertEqual(square[:32], (0x3000,) * 32)
        self.assertEqual(square[32:], (0xD000,) * 32)
        self.assertEqual((triangle[0], triangle[16], triangle[32], triangle[48]), (0x0000, 0x3000, 0x0000, 0xD000))
        self.assertEqual((saw[0], saw[32], saw[-1]), (0xD000, 0x0000, 0x2E80))

    def test_bridge_contains_complete_canonical_program(self):
        assets = build_srk_saturn_midi_bridge_assets()
        self.assertEqual(len(assets.program.records), 27)
        self.assertEqual(assets.program.duration_us, 1800000)
        self.assertLessEqual(len(assets.program.records), SATURN_MIDI_QUEUE_CAPACITY)
        self.assertEqual(len(assets.tone_bank), 3)
        self.assertTrue(assets.header_text.endswith("\n"))
        self.assertTrue(assets.source_text.endswith("\n"))

    def test_committed_generated_c_matches_python_source_of_truth(self):
        root = Path(__file__).resolve().parents[1]
        generated = root / "integrations" / "saturn" / "standalone"
        header = (generated / "srk_saturn_midi_generated.h").read_text(encoding="utf-8")
        source = (generated / "srk_saturn_midi_generated.c").read_text(encoding="utf-8")
        assets = build_srk_saturn_midi_bridge_assets()

        self.assertEqual(header, assets.header_text)
        self.assertEqual(source, assets.source_text)

    def test_generated_c_is_legacy_toolchain_friendly_and_not_live_hardware_code(self):
        assets = build_srk_saturn_midi_bridge_assets()
        combined = assets.header_text + assets.source_text

        self.assertIn("SRK_MIDI_MAILBOX_ADDRESS 0x00001000UL", combined)
        self.assertIn("SRK_MIDI_QUEUE_ADDRESS 0x00001100UL", combined)
        self.assertIn("SRK_MIDI_TONE_BANK_ADDRESS 0x00003000UL", combined)
        self.assertIn("SRK_MIDI_EVENT_COUNT 27UL", combined)
        self.assertIn("{1600000UL, 4u, 1u, 64u, 0u}", combined)
        self.assertNotIn("//", combined)
        self.assertNotIn("_Static_assert", combined)
        self.assertNotIn("volatile", combined)
        self.assertNotIn("0x25A00000", combined)
        self.assertNotIn("0x25B00000", combined)


if __name__ == "__main__":
    unittest.main()
