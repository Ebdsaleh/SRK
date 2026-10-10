"""Regression tests for the silent Saturn MIDI 68K physical-proof compiler gate."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof_compile_probe import (
    SaturnMidi68KPhysicalProofCompileProbeError,
    probe_saturn_midi_68k_physical_proof_compile,
    saturn_midi_68k_physical_proof_compile_flags,
)


def _fake_saturn_root(root: Path) -> Path:
    saturn = root / "Saturn-Dev"
    compiler = saturn / "SH_ELF" / "sh-elf" / "bin" / "sh-elf-gcc.exe"
    compiler.parent.mkdir(parents=True)
    compiler.write_bytes(b"fake-gcc")
    return saturn


class SaturnMidi68KPhysicalProofCompileProbeTests(unittest.TestCase):
    def test_compile_flags_match_standalone_c_policy(self):
        self.assertEqual(
            saturn_midi_68k_physical_proof_compile_flags(),
            (
                "-Wall",
                "-Werror",
                "-m2",
                "-O0",
                "-ffreestanding",
                "-fno-builtin",
            ),
        )

    def test_successful_probe_is_compile_only_and_does_not_execute_proof(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"
            calls = []

            def runner(argv, **kwargs):
                calls.append((tuple(argv), dict(kwargs)))
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(b"SH-ELF-MIDI-68K-PHYSICAL-PROOF-OBJECT")
                return SimpleNamespace(returncode=0, stdout=b"")

            result = probe_saturn_midi_68k_physical_proof_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertTrue(result.successful)
            self.assertTrue(result.object_path.is_file())
            self.assertEqual(len(calls), 1)
            argv, kwargs = calls[0]
            self.assertEqual(argv[1], "-c")
            self.assertIn("srk_saturn_midi_68k_physical_proof.c", argv[2])
            self.assertEqual(argv[3], "-o")
            for flag in saturn_midi_68k_physical_proof_compile_flags():
                self.assertIn(flag, argv)
            self.assertTrue(any(item.startswith("-I") for item in argv))
            self.assertFalse(kwargs["shell"])
            self.assertFalse(kwargs["check"])

            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["successful"])
            policy = report["policy"]
            self.assertTrue(policy["python_native_orchestration"])
            self.assertFalse(policy["shell_used"])
            self.assertFalse(policy["path_mutated"])
            self.assertTrue(policy["source_inputs_unchanged"])
            self.assertFalse(policy["linker_invoked"])
            self.assertFalse(policy["iso_builder_invoked"])
            self.assertFalse(policy["physical_proof_controller_called"])
            self.assertFalse(policy["hardware_adapter_called"])
            self.assertFalse(policy["runtime_called"])
            self.assertFalse(policy["sd_writes"])
            self.assertFalse(policy["sound_ram_writes"])
            self.assertFalse(policy["reset_vectors_changed"])
            self.assertFalse(policy["scsp_mmio"])
            self.assertFalse(policy["smpc_commands"])
            self.assertFalse(policy["mailbox_published"])
            self.assertFalse(policy["mc68ec000_program_installed"])
            self.assertFalse(policy["mc68ec000_execution"])

    def test_failed_compiler_is_preserved_as_evidence_without_object(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"

            def runner(argv, **kwargs):
                return SimpleNamespace(
                    returncode=1,
                    stdout=b"legacy compiler rejected physical-proof source",
                )

            result = probe_saturn_midi_68k_physical_proof_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertFalse(result.successful)
            self.assertIsNone(result.object_path)
            self.assertIn(
                "legacy compiler rejected physical-proof source",
                result.log_path.read_text(encoding="utf-8"),
            )
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["successful"])
            self.assertIsNone(report["object"])
            self.assertEqual(report["command"]["returncode"], 1)

    def test_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"
            output.mkdir()

            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCompileProbeError,
                "already exists",
            ):
                probe_saturn_midi_68k_physical_proof_compile(saturn, output)


if __name__ == "__main__":
    unittest.main()
