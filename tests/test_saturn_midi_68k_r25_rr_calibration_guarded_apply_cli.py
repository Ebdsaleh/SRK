"""CLI tests for explicit R25 RR16 guarded APPLY."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.tools.saturn_midi_68k_r25_rr_calibration_guarded_apply import main


class SaturnMidi68KR25RRCalibrationGuardedApplyCliTests(unittest.TestCase):
    def test_cli_reports_failure_without_exact_confirmation(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main([
                "--project", "candidate", "--card-root", "D:\\",
                "--guard-manifest", "guard.json", "--receipt", "receipt.json",
                "--category", "TEST", "--name", "SRK-Diagnostics-R25-RR16-CAL",
                "--confirm", "WRONG",
            ])
        self.assertEqual(code, 2)
        self.assertIn("DEPLOY-R25-RR16-CALIBRATION", stderr.getvalue())

    def test_cli_success_prints_reviewed_whole_card_boundary(self):
        destination = Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL")
        result = SimpleNamespace(
            pre_media=SimpleNamespace(project_root=Path("C:/candidate"), baseline_root=Path("C:/r24")),
            guard_manifest_path=Path("C:/guards/guard.json"),
            guard_manifest_sha256="5c17df50023c47955b4814eea648a506b3c30dafaa50ebfa157de65cffb9eac6",
            prepare_receipt_path=Path("C:/guards/receipt.json"),
            prepare_receipt_sha256="c78b7702f0ed27af0a0f0d42baa4d5754b102adfd1bb148055fb7be960980f6f",
            deployment=SimpleNamespace(
                plan=SimpleNamespace(destination_directory=destination),
                destination_bin=destination / "SRK-Diagnostics.bin",
                destination_cue=destination / "SRK-Diagnostics.cue",
                bin_sha256="a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71",
                cue_sha256="5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950",
            ),
            allowed_changed_paths=(
                "SAROO/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL",
                "SAROO/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL/SRK-Diagnostics.bin",
                "SAROO/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL/SRK-Diagnostics.cue",
            ),
        )
        stdout = StringIO()
        with (
            patch(
                "rikai_kotoba.tools.saturn_midi_68k_r25_rr_calibration_guarded_apply."
                "apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment",
                return_value=result,
            ),
            redirect_stdout(stdout),
        ):
            code = main([
                "--project", "candidate", "--card-root", "D:\\",
                "--guard-manifest", "guard.json", "--receipt", "receipt.json",
                "--category", "TEST", "--name", "SRK-Diagnostics-R25-RR16-CAL",
                "--confirm", "DEPLOY-R25-RR16-CALIBRATION",
            ])
        text = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Pre-write whole-card       : MATCH", text)
        self.assertIn("Post-write whole-card      : PASS", text)
        self.assertIn("Production RR selected     : NO", text)
        self.assertIn("R25 RR16 DEPLOYMENT VERIFIED", text)
        self.assertIn("Existing SAROO content was not overwritten or removed.", text)


if __name__ == "__main__":
    unittest.main()
