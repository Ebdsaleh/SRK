"""CLI regression for the R24 real-SMF whole-card guard."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_r24_physical_candidate_guarded_deployment as cli


class SaturnMidi68KR24PhysicalCandidateGuardedDeploymentCLITests(unittest.TestCase):
    def test_cli_surfaces_r24_token_external_chain_and_two_phase_boundary(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertEqual(cli.CONFIRMATION_TOKEN, "DEPLOY-R24-REAL-SMF-SONG-PROOF")
        self.assertIn("--expected-candidate-manifest-sha256", source)
        self.assertIn("--expected-candidate-report-sha256", source)
        self.assertIn("Song records / batches", source)
        self.assertIn("Note On / Off", source)
        self.assertIn("Peak polyphony", source)
        self.assertIn("READY FOR EXPLICIT R24 APPLY", source)
        self.assertIn("R24 DEPLOYMENT VERIFIED", source)
        self.assertIn("SAROO writes", source)


if __name__ == "__main__":
    unittest.main()
