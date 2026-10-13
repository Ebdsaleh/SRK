"""CLI contracts for the read-only R25 RR16 whole-card guard PREPARE command."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.tools import saturn_midi_68k_r25_rr_calibration_guard_prepare as _cli


class SaturnMidi68KR25RRCalibrationGuardPrepareCLITests(unittest.TestCase):
    def test_parser_exposes_no_apply_or_confirmation_option(self):
        options = {
            option
            for action in _cli._parser()._actions
            for option in action.option_strings
        }
        self.assertNotIn("--apply", options)
        self.assertNotIn("--confirm", options)
        self.assertNotIn("--expected-guard-manifest-sha256", options)

    def test_success_output_is_prepare_only_and_read_only(self):
        plan = SimpleNamespace(
            destination_directory=Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL")
        )
        pre = SimpleNamespace(
            project_root=Path("candidate"),
            baseline_root=Path("r24"),
            manifest_sha256="a" * 64,
            report_sha256="b" * 64,
            calibration_image_sha256="c" * 64,
            candidate_main_sha256="d" * 64,
            candidate_menu_sha256="e" * 64,
            runtime_after_sha256="f" * 64,
            proof_header_sha256="1" * 64,
            proof_source_sha256="2" * 64,
            deployable_bin_sha256="3" * 64,
            deployable_cue_sha256="4" * 64,
            plan=plan,
        )
        inv = SimpleNamespace(
            card_root=Path("D:/"),
            manifest_path=Path("C:/evidence/r25-card.json"),
            manifest_sha256="5" * 64,
            file_count=100,
            directory_count=20,
            total_file_bytes=123456,
            hashed_file_count=30,
        )
        result = SimpleNamespace(
            pre_media=pre,
            guard_inventory=inv,
            receipt_path=Path("C:/evidence/r25-receipt.json"),
            receipt_sha256="6" * 64,
        )
        output = StringIO()
        with patch.object(
            _cli,
            "prepare_saturn_midi_68k_r25_rr16_calibration_guard",
            return_value=result,
        ), redirect_stdout(output):
            status = _cli.main(
                [
                    "--project", "candidate",
                    "--card-root", "D:/",
                    "--guard-manifest", "C:/evidence/r25-card.json",
                    "--receipt", "C:/evidence/r25-receipt.json",
                    "--category", "TEST",
                    "--name", "SRK-Diagnostics-R25-RR16-CAL",
                ]
            )
        self.assertEqual(status, 0)
        rendered = output.getvalue()
        self.assertIn("Production RR selected     : NO", rendered)
        self.assertIn("Exact final guard          : MATCH", rendered)
        self.assertIn("Candidate/card binding     : PASS", rendered)
        self.assertIn("Destination freshness      : PASS", rendered)
        self.assertIn("SAROO writes               : NONE", rendered)
        self.assertIn("Apply path in this command : NONE", rendered)
        self.assertIn("Result                     : R25 RR16 PREPARE PASS", rendered)
        self.assertIn("Do not deploy yet", rendered)


if __name__ == "__main__":
    unittest.main()
