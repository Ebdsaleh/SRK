"""Regression tests for the off-card Saturn MIDI preload compiler gate."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_mailbox_compile_probe import (
    SaturnMidiMailboxCompileProbeError,
    probe_saturn_midi_mailbox_compile,
    saturn_midi_mailbox_compile_flags,
)


def _fake_saturn_root(root: Path) -> Path:
    saturn = root / "Saturn-Dev"
    compiler = saturn / "SH_ELF" / "sh-elf" / "bin" / "sh-elf-gcc.exe"
    compiler.parent.mkdir(parents=True)
    compiler.write_bytes(b"fake-gcc")
    return saturn


class SaturnMidiMailboxCompileProbeTests(unittest.TestCase):
    def test_compile_flags_match_production_policy(self):
        self.assertEqual(
            saturn_midi_mailbox_compile_flags(),
            (
                "-Wall",
                "-Werror",
                "-m2",
                "-O0",
                "-ffreestanding",
                "-fno-builtin",
            ),
        )

    def test_successful_probe_preserves_inputs_and_is_inert(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"
            calls = []

            def runner(argv, **kwargs):
                calls.append((tuple(argv), dict(kwargs)))
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(b"MAILBOX-OBJECT")
                return SimpleNamespace(returncode=0, stdout=b"")

            result = probe_saturn_midi_mailbox_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertTrue(result.successful)
            self.assertTrue(result.object_path.is_file())
            self.assertEqual(len(calls), 1)
            argv, kwargs = calls[0]
            self.assertEqual(argv[1], "-c")
            self.assertIn("srk_saturn_midi_mailbox.c", argv[2])
            for flag in saturn_midi_mailbox_compile_flags():
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
            self.assertFalse(policy["sd_writes"])
            self.assertFalse(policy["sound_ram_writes"])
            self.assertFalse(policy["scsp_mmio"])
            self.assertFalse(policy["mc68ec000_execution"])
            self.assertFalse(policy["producer_called"])

    def test_failed_compile_is_preserved_as_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"

            def runner(argv, **kwargs):
                return SimpleNamespace(returncode=1, stdout=b"mailbox producer rejected")

            result = probe_saturn_midi_mailbox_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertFalse(result.successful)
            self.assertIsNone(result.object_path)
            self.assertIn(
                "mailbox producer rejected",
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

            with self.assertRaisesRegex(SaturnMidiMailboxCompileProbeError, "already exists"):
                probe_saturn_midi_mailbox_compile(saturn, output)


if __name__ == "__main__":
    unittest.main()
