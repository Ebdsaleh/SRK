"""CLI regression for the R21 full-state whole-card guard."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_state_physical_candidate_guarded_deployment as cli


class SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentCLITests(unittest.TestCase):
    def test_cli_surfaces_r21_token_and_full_state_contract(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertIn("DEPLOY-R21-RESIDENT-STATE-PROOF", source)
        self.assertIn("Proof records            : 20", source)
        self.assertIn("Summary words verified", source)
        self.assertIn("Controller words verified", source)
        self.assertIn("Active-note words verify", source)
        self.assertIn("READY FOR EXPLICIT R21 APPLY", source)
        self.assertIn("R21 DEPLOYMENT VERIFIED", source)


if __name__ == "__main__":
    unittest.main()
