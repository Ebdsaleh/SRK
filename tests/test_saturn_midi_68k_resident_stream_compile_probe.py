"""Regression tests for the continuous stream-service compiler gate."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_compile_probe import (
    SaturnMidi68KResidentStreamCompileProbeError,
    probe_saturn_midi_68k_resident_stream_compile,
    saturn_midi_68k_resident_stream_compile_flags,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
)


class SaturnMidi68KResidentStreamCompileProbeTests(unittest.TestCase):
    def test_compile_policy_matches_legacy_production_flags(self):
        self.assertEqual(
            saturn_midi_68k_resident_stream_compile_flags(),
            ("-Wall", "-Werror", "-m2", "-O0", "-ffreestanding", "-fno-builtin"),
        )

    def test_existing_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KResidentStreamCompileProbeError, "already exists"):
                probe_saturn_midi_68k_resident_stream_compile(root, output)

    def test_mock_compile_builds_both_objects_and_records_scheduler_policy(self):
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
            calls = []

            def runner(argv, **_kwargs):
                calls.append(tuple(argv))
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(("object:" + object_path.name).encode("ascii"))
                return SimpleNamespace(returncode=0, stdout=b"")

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_resident_stream_compile(
                    root,
                    output,
                    _runner=runner,
                )

            self.assertTrue(result.successful)
            self.assertEqual(len(calls), 2)
            self.assertTrue(result.resident_object_path.is_file())
            self.assertTrue(result.producer_object_path.is_file())
            image = build_srk_saturn_midi_68k_resident_stream_service_image()
            self.assertEqual(result.image_sha256, image.sha256)
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(
                report["schema"],
                "srk.saturn.midi-68k-resident-stream-compile-probe.v1",
            )
            self.assertTrue(report["image"]["multi_batch_refill"])
            self.assertTrue(report["image"]["timestamp_scheduler"])
            self.assertTrue(report["image"]["state_persistent_across_refills"])
            self.assertFalse(report["image"]["scsp_access"])
            self.assertFalse(report["policy"]["sd_writes"])
            self.assertFalse(report["policy"]["mc68ec000_execution"])

    def test_failed_compile_does_not_fabricate_objects_or_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "gate"
            environment = SimpleNamespace(
                compiler=SimpleNamespace(path_for=lambda _name: compiler)
            )
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_resident_stream_compile(
                    root,
                    output,
                    _runner=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=1,
                        stdout=b"compile failed",
                    ),
                )
            self.assertFalse(result.successful)
            self.assertIsNone(result.resident_object_path)
            self.assertIsNone(result.producer_object_path)
            self.assertIn("compile failed", result.log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
