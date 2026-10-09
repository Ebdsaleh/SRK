"""Regression lock for player-facing VDP1 shoulder-roll polarity."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
VDP1_C = ROOT / "integrations" / "saturn" / "diagnostics" / "srk_diag_vdp1.c"


class SaturnVdp1RollPolarityTests(unittest.TestCase):
    def test_l_is_counter_clockwise_and_r_is_clockwise(self):
        source = VDP1_C.read_text(encoding="utf-8")

        l_block = re.compile(
            r"if\(\(held_buttons & SRK_DIAG_BUTTON_L\).*?"
            r"velocity = \(srk_s32\)state->velocity_z \+ SRK_DIAG_VDP1_ACCEL_Q8;",
            re.DOTALL,
        )
        r_block = re.compile(
            r"else if\(\(held_buttons & SRK_DIAG_BUTTON_R\).*?"
            r"velocity = \(srk_s32\)state->velocity_z - SRK_DIAG_VDP1_ACCEL_Q8;",
            re.DOTALL,
        )

        self.assertRegex(source, l_block)
        self.assertRegex(source, r_block)
        self.assertIn("L rolls left/CCW, R rolls right/CW", source)


if __name__ == "__main__":
    unittest.main()
