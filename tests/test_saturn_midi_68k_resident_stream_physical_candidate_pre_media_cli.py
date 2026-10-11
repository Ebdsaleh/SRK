"""CLI safety regression for the read-only R22 pre-media gate."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_stream_physical_candidate_pre_media_gate as cli


class SaturnMidi68KResidentStreamPhysicalCandidatePreMediaCLITests(unittest.TestCase):
    def test_cli_is_read_only_and_surfaces_timing_refill_boundary(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn("Proof records", source)
        self.assertIn("Batch split", source)
        self.assertIn("0us proof", source)
        self.assertIn("15ms proof", source)
        self.assertIn("32ms proof", source)
        self.assertIn("Refill at old clock", source)
        self.assertIn("40ms proof", source)
        self.assertIn("Full-state proof", source)
        self.assertIn("SAROO writes", source)
        self.assertIn("NONE", source)
        self.assertNotIn("--apply", source)
        self.assertNotIn("--confirm", source)


if __name__ == "__main__":
    unittest.main()
