"""Presentation contracts for the Stage 6B Saturn audio proof."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "integrations" / "saturn" / "diagnostics" / "srk_diag_app.c"


class SaturnStage6BPresentationTests(unittest.TestCase):
    def test_audio_screen_identifies_stage6_and_disc_pcm_control(self):
        app_c = APP.read_text(encoding="utf-8")

        self.assertIn("Stages 1-6: deterministic PCM proofs", app_c)
        self.assertNotIn("Stages 1-5: deterministic PCM proofs", app_c)
        self.assertIn("DOWN+Z Mixed pair  DOWN+Y Disc PCM", app_c)
        self.assertIn("START Stop + return to diagnostics menu", app_c)


if __name__ == "__main__":
    unittest.main()
