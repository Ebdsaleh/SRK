"""CLI regression for the read-only R20 resident-decoder pre-media gate."""

from __future__ import annotations

from pathlib import Path
import unittest


_ROOT = Path(__file__).resolve().parents[1]


class SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaCliTests(unittest.TestCase):
    def test_cli_exposes_index_7_rd_telemetry_and_no_apply_option(self):
        source = (
            _ROOT
            / "src/rikai_kotoba/tools/saturn_midi_68k_resident_decoder_physical_candidate_pre_media_gate.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ACKNOWLEDGED / sequence 1 / index 7 / error 0", source)
        self.assertIn("RD v1 / processed 7 / current 7 / ready 1", source)
        self.assertIn("SAROO writes            : NONE", source)
        self.assertIn("Do not deploy from this command", source)
        self.assertNotIn('add_argument("--apply"', source)


if __name__ == "__main__":
    unittest.main()
