"""Regression contracts for the inert R25 RR compiler matrix."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_r25_compile_probe import (
    SaturnMidi68KR25CompileProbeError,
    probe_saturn_midi_68k_r25_rr_compile_matrix,
    saturn_midi_68k_r25_compile_flags,
)


class SaturnMidi68KR25CompileProbeTests(unittest.TestCase):
    def test_compile_policy_matches_legacy_sh_elf_flags(self):
        self.assertEqual(
            saturn_midi_68k_r25_compile_flags(),
            ("-Wall", "-Werror", "-m2", "-O0", "-ffreestanding", "-fno-builtin"),
        )

    def test_existing_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KR25CompileProbeError, "already exists"):
                probe_saturn_midi_68k_r25_rr_compile_matrix(root, output)

    def test_mock_compile_builds_all_32_inert_rr_objects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "matrix"
            environment = SimpleNamespace(
                compiler=SimpleNamespace(
                    path_for=lambda name: compiler if name == "sh-elf-gcc" else None
                )
            )
            calls = []

            def runner(argv, **_kwargs):
                calls.append(tuple(argv))
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(("object:" + object_path.parent.name).encode("ascii"))
                return SimpleNamespace(returncode=0, stdout=b"")

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r25_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_r25_rr_compile_matrix(
                    root, output, _runner=runner
                )

            self.assertTrue(result.successful)
            self.assertEqual(len(calls), 32)
            self.assertEqual(tuple(entry.release_rate for entry in result.entries), tuple(range(32)))
            self.assertEqual(len({entry.image_sha256 for entry in result.entries}), 32)
            self.assertTrue(all(entry.object_sha256 for entry in result.entries))
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "srk.saturn.midi-68k-r25-rr-compile-matrix.v1")
            self.assertEqual(len(report["matrix"]), 32)
            self.assertFalse(report["policy"]["rr_selected"])
            self.assertFalse(report["policy"]["physical_measurements_supplied"])
            self.assertFalse(report["policy"]["linker_invoked"])
            self.assertFalse(report["policy"]["sd_writes"])
            self.assertFalse(report["policy"]["scsp_mmio_executed"])

    def test_failed_compile_records_failure_without_fabricating_object_hashes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "matrix"
            environment = SimpleNamespace(
                compiler=SimpleNamespace(path_for=lambda _name: compiler)
            )
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r25_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_r25_rr_compile_matrix(
                    root,
                    output,
                    _runner=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=1, stdout=b"compile failed"
                    ),
                )
            self.assertFalse(result.successful)
            self.assertTrue(all(entry.object_sha256 is None for entry in result.entries))
            self.assertIn("compile failed", result.log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
