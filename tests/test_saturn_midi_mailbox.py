"""Regression tests for the still-uninvoked Saturn MIDI preload producer."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_mailbox import (
    SATURN_MIDI_MAILBOX_FLAG_READY,
    SATURN_MIDI_MAILBOX_WORD_COUNT,
    SATURN_MIDI_PRELOAD_WRITE_SEQUENCE,
    build_srk_saturn_midi_preload_image,
    render_srk_saturn_midi_mailbox_header,
    render_srk_saturn_midi_mailbox_source,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _REPO_ROOT / "integrations" / "saturn" / "standalone"


class SaturnMidiMailboxTests(unittest.TestCase):
    def test_canonical_preload_image_is_stable(self):
        image = build_srk_saturn_midi_preload_image()
        self.assertEqual(len(image.mailbox_words), SATURN_MIDI_MAILBOX_WORD_COUNT)
        self.assertEqual(len(image.queue_words), 108)
        self.assertEqual(len(image.tone_words), 192)
        self.assertEqual(image.byte_size, 624)
        self.assertEqual(
            image.sha256,
            "4b9ace091bdbf23fa1536e8b9373604ef57cd172edf506a1e37db9b29cbb2451",
        )

    def test_mailbox_publishes_one_bounded_batch(self):
        image = build_srk_saturn_midi_preload_image()
        words = image.mailbox_words
        self.assertEqual(words[0:3], (0x5352, 0x4B4D, 1))
        self.assertEqual(words[3], SATURN_MIDI_MAILBOX_FLAG_READY)
        self.assertEqual(words[4], SATURN_MIDI_PRELOAD_WRITE_SEQUENCE)
        self.assertEqual(words[5], 0)
        self.assertEqual(words[6], 27)
        self.assertEqual(words[7], 0)
        self.assertEqual(words[8], 32)
        self.assertEqual(words[9], 27)
        self.assertEqual(words[10:12], (0, 0))

    def test_queue_word_encoding_is_big_endian_srkm(self):
        image = build_srk_saturn_midi_preload_image()
        self.assertEqual(image.queue_words[0:4], (0x0000, 0x0000, 0x0400, 0x0000))
        self.assertEqual(
            image.queue_words[-4:],
            (0x0018, 0x6A00, 0x0401, 0x4000),
        )

    def test_committed_c_and_header_equal_python_renderer(self):
        header = (_STANDALONE / "srk_saturn_midi_mailbox.h").read_text(encoding="utf-8")
        source = (_STANDALONE / "srk_saturn_midi_mailbox.c").read_text(encoding="utf-8")
        self.assertEqual(header, render_srk_saturn_midi_mailbox_header())
        self.assertEqual(source, render_srk_saturn_midi_mailbox_source())

    def test_producer_is_hardware_shaped_but_not_launched(self):
        source = render_srk_saturn_midi_mailbox_source()
        self.assertIn("0x25A00000UL", source)
        self.assertIn("SRK_MIDI_MAILBOX_FLAG_READY", source)
        self.assertIn("Publish READY last", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)
        self.assertNotIn("srk_saturn_midi_preload_publish();", source)


if __name__ == "__main__":
    unittest.main()
