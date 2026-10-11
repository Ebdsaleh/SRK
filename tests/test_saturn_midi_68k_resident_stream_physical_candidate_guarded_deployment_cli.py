"""CLI regression for the R22 stream/scheduler whole-card guard."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_stream_physical_candidate_guarded_deployment as cli


class SaturnMidi68KResidentStreamPhysicalCandidateGuardedDeploymentCLITests(unittest.TestCase):
    def test_cli_surfaces_r22_token_and_timing_refill_contract(self):
        source = Path(cli.__file__).read_text(encoding="utf-8")
        self.assertEqual(cli.CONFIRMATION_TOKEN, "DEPLOY-R22-STREAM-SCHEDULER-PROOF")
        self.assertIn("Proof records", source)
        self.assertIn("Batch split", source)
        self.assertIn("0us proof", source)
        self.assertIn("15ms proof", source)
        self.assertIn("32ms proof", source)
        self.assertIn("Refill at old clock", source)
        self.assertIn("40ms proof", source)
        self.assertIn("READY FOR EXPLICIT R22 APPLY", source)
        self.assertIn("R22 DEPLOYMENT VERIFIED", source)


if __name__ == "__main__":
    unittest.main()
