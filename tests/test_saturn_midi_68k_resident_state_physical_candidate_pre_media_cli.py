"""CLI safety regression for the Phase-B full-state pre-media gate."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_state_physical_candidate_pre_media_gate as cli


class SaturnMidi68KResidentStatePhysicalCandidatePreMediaCLITests(unittest.TestCase):
    def test_cli_is_read_only_and_surfaces_complete_state_boundary(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn("Summary words verified", source)
        self.assertIn("Controller words verify", source)
        self.assertIn("Active-note words verify", source)
        self.assertIn("Full-state proof", source)
        self.assertIn("SAROO writes", source)
        self.assertIn("NONE", source)
        self.assertNotIn("--apply", source)
        self.assertNotIn("--confirm", source)


if __name__ == "__main__":
    unittest.main()
