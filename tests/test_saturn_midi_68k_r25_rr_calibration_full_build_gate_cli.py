"""CLI contracts for the R25 RR physical calibration full-build gate."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.tools import saturn_midi_68k_r25_rr_calibration_full_build_gate as _cli


class SaturnMidi68KR25RRCalibrationFullBuildGateCLITests(unittest.TestCase):
    def test_rr_range_is_enforced_by_parser(self):
        stderr = StringIO()
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            _cli._parser().parse_args(
                [
                    "--baseline-project",
                    "r24",
                    "--output",
                    "r25",
                    "--release-rate",
                    "32",
                ]
            )
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("RR must be an integer from 0 through 31", stderr.getvalue())

    def test_success_output_keeps_off_card_and_production_rr_unset(self):
        prepared = SimpleNamespace(
            baseline_root=Path("r24"),
            output_root=Path("r25"),
            release_rate=16,
            eg1_word=0x001F,
            eg2_word=0x3C10,
            baseline_manifest_sha256="a" * 64,
            baseline_report_sha256="b" * 64,
            baseline_bin_sha256="c" * 64,
            baseline_cue_sha256="d" * 64,
            calibration_image_sha256="e" * 64,
            resident_source_sha256="1" * 64,
            resident_header_sha256="2" * 64,
            voice_header_sha256="3" * 64,
            candidate_main_sha256="4" * 64,
            candidate_menu_sha256="5" * 64,
            runtime_before_sha256="6" * 64,
            runtime_after_sha256="7" * 64,
            proof_header_sha256="8" * 64,
            proof_source_sha256="9" * 64,
        )
        build = SimpleNamespace(
            commands=(),
            artifacts=(),
            log_path=Path("r25/SRK_STANDALONE_BUILD_LOG.txt"),
            report_path=Path("r25/SRK_STANDALONE_BUILD.json"),
            successful=True,
        )
        stdout = StringIO()
        with patch.object(
            _cli,
            "run_saturn_midi_68k_r25_rr_calibration_full_build_gate",
            return_value=SimpleNamespace(prepared=prepared, build=build),
        ), redirect_stdout(stdout):
            result = _cli.main(
                [
                    "--baseline-project",
                    "r24",
                    "--output",
                    "r25",
                    "--release-rate",
                    "16",
                ]
            )
        self.assertEqual(result, 0)
        rendered = stdout.getvalue()
        self.assertIn("RR probe                     : 16", rendered)
        self.assertIn("Measurement mode             : OPERATOR-OBSERVED AUDIO", rendered)
        self.assertIn("SCSP envelope readback       : NO", rendered)
        self.assertIn("Production RR selected       : NO", rendered)
        self.assertIn("SAROO writes                 : NONE", rendered)
        self.assertIn("Result                       : SUCCESS", rendered)
        self.assertIn("Do not copy or deploy it to SAROO yet.", rendered)


if __name__ == "__main__":
    unittest.main()
