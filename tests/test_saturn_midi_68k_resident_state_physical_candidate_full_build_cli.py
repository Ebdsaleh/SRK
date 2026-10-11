"""CLI regression for the Phase-B full-state physical candidate."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_state_physical_candidate_full_build_gate as cli


class SaturnMidi68KResidentStatePhysicalCandidateCLITests(unittest.TestCase):
    def test_cli_is_build_only_and_prints_full_state_boundary(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn("Summary words verified", source)
        self.assertIn("Controller words verify", source)
        self.assertIn("Active-note words verify", source)
        self.assertIn("CH3 program/bank", source)
        self.assertIn("PASS requires", source)
        self.assertIn("SAROO writes", source)
        self.assertNotIn("--apply", source)
        self.assertNotIn("--card-root", source)


if __name__ == "__main__":
    unittest.main()
