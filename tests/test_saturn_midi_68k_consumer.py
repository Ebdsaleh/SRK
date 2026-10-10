"""Regression tests for the protocol-only MC68EC000 MIDI consumer image."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_consumer import (
    SATURN_MIDI_68K_ERROR_CONTRACT,
    SATURN_MIDI_68K_ERROR_MAGIC,
    SATURN_MIDI_68K_ERROR_RECORD,
    SATURN_MIDI_68K_FIRST_RECORD_WORDS,
    SATURN_MIDI_68K_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_STACK_ADDRESS,
    build_srk_saturn_midi_68k_consumer_image,
    render_srk_saturn_midi_68k_header,
    render_srk_saturn_midi_68k_source,
    simulate_srk_saturn_midi_68k_protocol,
)
from rikai_kotoba.hardware.saturn.midi_bridge import SATURN_MIDI_MAILBOX_ADDRESS
from rikai_kotoba.hardware.saturn.midi_mailbox import build_srk_saturn_midi_preload_image


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _REPO_ROOT / "integrations" / "saturn" / "standalone"


class SaturnMidi68KConsumerTests(unittest.TestCase):
    def test_program_image_is_stable_and_bounded(self):
        image = build_srk_saturn_midi_68k_consumer_image()
        self.assertEqual(SATURN_MIDI_68K_PROGRAM_ADDRESS, 0x00000600)
        self.assertEqual(SATURN_MIDI_68K_STACK_ADDRESS, 0x0007FFF0)
        self.assertEqual(len(image.words), 81)
        self.assertEqual(image.byte_size, 162)
        self.assertEqual(image.end_address, 0x000006A2)
        self.assertLess(image.end_address, SATURN_MIDI_MAILBOX_ADDRESS)
        self.assertEqual(
            image.sha256,
            "2a0f30068be2815953569e2717af6c92197b08897fdca744607f5b4bee14e5c2",
        )

    def test_program_contains_reviewed_poll_ack_and_hold_opcodes(self):
        image = build_srk_saturn_midi_68k_consumer_image()
        words = image.words
        self.assertEqual(words[0:5], (0x3038, 0x1006, 0x0240, 0x0001, 0x67F6))
        self.assertIn(0x31FC, words)
        self.assertIn(0x31C0, words)
        self.assertEqual(words[-1], 0x60FE)
        self.assertEqual(words[60], 0x60FE)

    def test_canonical_first_record_is_exact_protocol_proof_record(self):
        preload = build_srk_saturn_midi_preload_image()
        self.assertEqual(preload.queue_words[:4], SATURN_MIDI_68K_FIRST_RECORD_WORDS)
        self.assertEqual(SATURN_MIDI_68K_FIRST_RECORD_WORDS, (0, 0, 0x0400, 0))

    def test_protocol_model_acknowledges_exactly_one_record(self):
        preload = build_srk_saturn_midi_preload_image()
        result = simulate_srk_saturn_midi_68k_protocol(
            preload.mailbox_words,
            preload.queue_words,
        )
        self.assertEqual(result.status, "acknowledged")
        self.assertEqual(result.error_code, 0)
        self.assertEqual(result.mailbox_words[7], 1)
        self.assertEqual(result.mailbox_words[5], result.mailbox_words[4])
        self.assertEqual(result.mailbox_words[10], 0)

    def test_protocol_model_reports_bounded_failures(self):
        preload = build_srk_saturn_midi_preload_image()

        bad_magic = list(preload.mailbox_words)
        bad_magic[0] ^= 1
        result = simulate_srk_saturn_midi_68k_protocol(tuple(bad_magic), preload.queue_words)
        self.assertEqual((result.status, result.error_code), ("error-magic", SATURN_MIDI_68K_ERROR_MAGIC))

        bad_capacity = list(preload.mailbox_words)
        bad_capacity[8] = 31
        result = simulate_srk_saturn_midi_68k_protocol(tuple(bad_capacity), preload.queue_words)
        self.assertEqual(
            (result.status, result.error_code),
            ("error-contract", SATURN_MIDI_68K_ERROR_CONTRACT),
        )

        bad_queue = list(preload.queue_words)
        bad_queue[2] ^= 1
        result = simulate_srk_saturn_midi_68k_protocol(preload.mailbox_words, tuple(bad_queue))
        self.assertEqual(
            (result.status, result.error_code),
            ("error-record", SATURN_MIDI_68K_ERROR_RECORD),
        )

    def test_committed_c_matches_renderer_and_remains_inert(self):
        header = (_STANDALONE / "srk_saturn_midi_68k_program.h").read_text(encoding="utf-8")
        source = (_STANDALONE / "srk_saturn_midi_68k_program.c").read_text(encoding="utf-8")
        self.assertEqual(header, render_srk_saturn_midi_68k_header())
        self.assertEqual(source, render_srk_saturn_midi_68k_source())
        self.assertNotIn("volatile", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)


if __name__ == "__main__":
    unittest.main()
