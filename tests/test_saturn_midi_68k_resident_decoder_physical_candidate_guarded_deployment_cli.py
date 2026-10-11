"""CLI regression for the R20 whole-card guarded deployment."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
)
from rikai_kotoba.tools.saturn_midi_68k_resident_decoder_physical_candidate_guarded_deployment import (
    _parser,
    _print_pre_media,
)


class SaturnMidi68KResidentDecoderPhysicalCandidateGuardedDeploymentCLITests(unittest.TestCase):
    def test_cli_prints_r20_contract_and_exposes_specific_apply_token(self):
        result = SimpleNamespace(
            manifest_sha256="1" * 64,
            report_sha256="2" * 64,
            image_sha256="3" * 64,
            deployable_bin_sha256="4" * 64,
            deployable_cue_sha256="5" * 64,
        )
        output = StringIO()
        with redirect_stdout(output):
            _print_pre_media(result)
        text = output.getvalue()
        self.assertIn("Decoder image SHA-256    : " + ("3" * 64), text)
        self.assertIn("all 7 SRKM v1 opcodes exactly once", text)
        self.assertIn("ACKNOWLEDGED / sequence 1 / index 7 / error 0", text)
        self.assertIn("RD v1 / processed 7 / current 7 / ready 1", text)
        self.assertIn("MIDI-driven SCSP note    : NO", text)

        help_text = _parser().format_help()
        self.assertIn("--apply", help_text)
        self.assertIn(CONFIRMATION_TOKEN, help_text)
        self.assertEqual(CONFIRMATION_TOKEN, "DEPLOY-R20-RESIDENT-DECODER-PROOF")


if __name__ == "__main__":
    unittest.main()
