"""Exact image lock for the post-R19 general silent resident decoder."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    build_srk_saturn_midi_68k_resident_decoder_image,
)


class SaturnMidi68KResidentDecoderImageLockTests(unittest.TestCase):
    def test_exact_reviewed_image_geometry_and_hash(self):
        image = build_srk_saturn_midi_68k_resident_decoder_image()

        self.assertEqual(image.word_count, 239)
        self.assertEqual(image.byte_size, 478)
        self.assertEqual(image.end_address, 0x000041DE)
        self.assertEqual(
            image.sha256,
            "d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4",
        )


if __name__ == "__main__":
    unittest.main()
