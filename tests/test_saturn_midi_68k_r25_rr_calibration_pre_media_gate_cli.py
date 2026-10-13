"""CLI contracts for the R25 RR16 read-only pre-media gate."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.tools import saturn_midi_68k_r25_rr_calibration_pre_media_gate as _cli


class SaturnMidi68KR25RRCalibrationPreMediaGateCLITests(unittest.TestCase):
    def test_success_output_is_explicitly_read_only(self):
        plan = SimpleNamespace(
            card_root=Path("D:/"),
            category_directory=Path("D:/saroo/ISO/TEST"),
            destination_directory=Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL"),
            source_bin=Path("candidate/build/SRK-Diagnostics/SRK-Diagnostics.bin"),
            source_cue=Path("candidate/build/SRK-Diagnostics/SRK-Diagnostics.cue"),
            bin_size=338688,
            cue_size=81,
        )
        result = SimpleNamespace(
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
            sector_count=144,
            raw_bytes=338688,
            plan=plan,
        )
        output = StringIO()
        with patch.object(
            _cli,
            "inspect_saturn_midi_68k_r25_rr_calibration_pre_media",
            return_value=result,
        ), redirect_stdout(output):
            status = _cli.main(
                [
                    "--project", "candidate",
                    "--card-root", "D:/",
                    "--category", "TEST",
                    "--name", "SRK-Diagnostics-R25-RR16-CAL",
                ]
            )
        self.assertEqual(status, 0)
        rendered = output.getvalue()
        self.assertIn("Production RR selected     : NO", rendered)
        self.assertIn("Accepted R24 chain         : PASS", rendered)
        self.assertIn("Runtime reconstruction     : PASS", rendered)
        self.assertIn("SAROO destination          : FRESH", rendered)
        self.assertIn("SAROO writes               : NONE", rendered)
        self.assertIn("Result                     : PRE-MEDIA GATE PASS", rendered)
        self.assertIn("Do not deploy from this command", rendered)


if __name__ == "__main__":
    unittest.main()
