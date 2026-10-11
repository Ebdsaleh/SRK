"""CLI regression for the silent seven-record resident-decoder candidate build."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.tools import saturn_midi_68k_resident_decoder_physical_candidate_full_build_gate as cli


class SaturnMidi68KResidentDecoderPhysicalCandidateCLITests(unittest.TestCase):
    def test_cli_prints_seven_record_silent_boundary_without_card_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepared = SimpleNamespace(
                baseline_root=root / "baseline",
                output_root=root / "candidate",
                baseline_manifest_sha256="1" * 64,
                baseline_report_sha256="2" * 64,
                baseline_bin_sha256="3" * 64,
                baseline_cue_sha256="4" * 64,
                image_sha256="5" * 64,
                candidate_main_sha256="6" * 64,
                candidate_menu_sha256="7" * 64,
                runtime_after_sha256="8" * 64,
                proof_records=7,
                proof_final_time_us=7000,
            )
            build = SimpleNamespace(
                commands=(),
                artifacts=(),
                project_root=root / "candidate",
                log_path=root / "candidate" / "log.txt",
                report_path=root / "candidate" / "report.json",
                successful=True,
            )
            fake = SimpleNamespace(prepared=prepared, build=build)
            out = StringIO()
            err = StringIO()
            argv = [
                "--baseline-project", str(root / "baseline"),
                "--output", str(root / "candidate"),
                "--expected-baseline-bin-sha256", "3" * 64,
                "--expected-baseline-cue-sha256", "4" * 64,
                "--expected-image-sha256", "5" * 64,
                "--expected-compiler-source-sha256", "9" * 64,
                "--expected-compiler-header-sha256", "a" * 64,
                "--expected-compiler-object-sha256", "b" * 64,
                "--expected-runtime-after-sha256", "8" * 64,
            ]
            with patch.object(cli, "run_midi_68k_resident_decoder_physical_candidate_full_build_gate", return_value=fake):
                with redirect_stdout(out), redirect_stderr(err):
                    code = cli.main(argv)
            text = out.getvalue()
            self.assertEqual(code, 0)
            self.assertEqual(err.getvalue(), "")
            self.assertIn("Proof records           : 7", text)
            self.assertIn("index 7 / error 0", text)
            self.assertIn("RD v1 / processed 7 / current 7 / ready 1", text)
            self.assertIn("MIDI-driven SCSP note   : NO", text)
            self.assertIn("SAROO writes            : NONE", text)
            self.assertIn("Do not deploy", text)


if __name__ == "__main__":
    unittest.main()
