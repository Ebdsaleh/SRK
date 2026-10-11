"""Regression tests for the Phase-B resident state decoder compile gate."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder import (
    build_srk_saturn_midi_68k_resident_state_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_compile_probe import (
    SaturnMidi68KResidentStateDecoderCompileProbeError,
    probe_saturn_midi_68k_resident_state_decoder_compile,
    saturn_midi_68k_resident_state_decoder_compile_flags,
)


class SaturnMidi68KResidentStateDecoderCompileProbeTests(unittest.TestCase):
    def test_compile_policy_matches_production_legacy_flags(self):
        self.assertEqual(
            saturn_midi_68k_resident_state_decoder_compile_flags(),
            ("-Wall", "-Werror", "-m2", "-O0", "-ffreestanding", "-fno-builtin"),
        )

    def test_existing_output_is_rejected_before_compiler_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "already-exists"
            output.mkdir()
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStateDecoderCompileProbeError,
                "already exists",
            ):
                probe_saturn_midi_68k_resident_state_decoder_compile(root, output)

    def test_mock_legacy_compile_preserves_inputs_and_records_exact_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "gate"

            environment = SimpleNamespace(
                compiler=SimpleNamespace(
                    path_for=lambda name: compiler if name == "sh-elf-gcc" else None
                )
            )

            def runner(argv, **_kwargs):
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(b"phase-b-object")
                return SimpleNamespace(returncode=0, stdout=b"")

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_resident_state_decoder_compile(
                    root,
                    output,
                    _runner=runner,
                )

            self.assertTrue(result.successful)
            self.assertTrue(result.object_path.is_file())
            image = build_srk_saturn_midi_68k_resident_state_decoder_image()
            self.assertEqual(result.image_sha256, image.sha256)
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                report["schema"],
                "srk.saturn.midi-68k-resident-state-decoder-compile-probe.v1",
            )
            self.assertTrue(report["image"]["dynamic_state_mutation"])
            self.assertFalse(report["image"]["scsp_access"])
            self.assertFalse(report["policy"]["sd_writes"])
            self.assertFalse(report["policy"]["mc68ec000_execution"])

    def test_failed_compiler_is_reported_without_fabricating_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "gate"
            environment = SimpleNamespace(
                compiler=SimpleNamespace(path_for=lambda _name: compiler)
            )

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_resident_state_decoder_compile(
                    root,
                    output,
                    _runner=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=1,
                        stdout=b"compile failed",
                    ),
                )

            self.assertFalse(result.successful)
            self.assertIsNone(result.object_path)
            self.assertIn("compile failed", result.log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
