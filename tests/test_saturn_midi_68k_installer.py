"""Regression tests for the still-uncalled Saturn MIDI MC68EC000 installer."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_installer import (
    SATURN_MIDI_68K_DUMMY_LOOP_ADDRESS,
    SATURN_MIDI_68K_RESET_PC_VECTOR_ADDRESS,
    SATURN_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,
    SATURN_MIDI_68K_SH2_SOUND_RAM_BASE,
    build_srk_saturn_midi_68k_install_image,
    render_srk_saturn_midi_68k_installer_header,
    render_srk_saturn_midi_68k_installer_source,
)
from rikai_kotoba.hardware.saturn.midi_bridge import SATURN_MIDI_MAILBOX_ADDRESS


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _REPO_ROOT / "integrations" / "saturn" / "standalone"


class SaturnMidi68KInstallerTests(unittest.TestCase):
    def test_install_image_matches_reviewed_program_contract(self):
        image = build_srk_saturn_midi_68k_install_image()
        self.assertEqual(image.program_address, 0x00000600)
        self.assertEqual(image.stack_address, 0x0007FFF0)
        self.assertEqual(len(image.program_words), 81)
        self.assertEqual(image.program_byte_size, 162)
        self.assertEqual(image.program_end_address, 0x000006A2)
        self.assertEqual(
            image.program_sha256,
            "2a0f30068be2815953569e2717af6c92197b08897fdca744607f5b4bee14e5c2",
        )

    def test_install_regions_stay_between_dummy_loop_and_mailbox(self):
        image = build_srk_saturn_midi_68k_install_image()
        self.assertGreaterEqual(image.program_address, SATURN_MIDI_68K_DUMMY_LOOP_ADDRESS + 2)
        self.assertLessEqual(image.program_end_address, SATURN_MIDI_MAILBOX_ADDRESS)
        self.assertEqual(SATURN_MIDI_68K_RESET_SSP_VECTOR_ADDRESS, 0)
        self.assertEqual(SATURN_MIDI_68K_RESET_PC_VECTOR_ADDRESS, 4)
        self.assertEqual(SATURN_MIDI_68K_SH2_SOUND_RAM_BASE, 0x25A00000)

    def test_committed_c_and_header_equal_python_renderer(self):
        header = (_STANDALONE / "srk_saturn_midi_68k_installer.h").read_text(encoding="utf-8")
        source = (_STANDALONE / "srk_saturn_midi_68k_installer.c").read_text(encoding="utf-8")
        self.assertEqual(header, render_srk_saturn_midi_68k_installer_header())
        self.assertEqual(source, render_srk_saturn_midi_68k_installer_source())

    def test_installer_publishes_program_before_reset_vectors(self):
        source = render_srk_saturn_midi_68k_installer_source()
        program_copy = source.index("SRK_MIDI_68K_PROGRAM_ADDRESS + (index * 2UL)")
        ssp_write = source.index("SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,", program_copy)
        pc_write = source.index("SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,", ssp_write)
        self.assertLess(program_copy, ssp_write)
        self.assertLess(ssp_write, pc_write)
        self.assertIn("return srk_saturn_midi_68k_verify_install();", source)

    def test_installer_has_no_launch_or_scsp_control(self):
        source = render_srk_saturn_midi_68k_installer_source()
        self.assertIn("0x25A00000UL", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)
        self.assertNotIn("srk_saturn_midi_preload_publish", source)
        self.assertNotIn("SRK_AUDIO_SMPC", source)


if __name__ == "__main__":
    unittest.main()
