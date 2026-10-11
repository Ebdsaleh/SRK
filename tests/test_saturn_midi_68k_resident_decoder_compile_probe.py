"""Regression tests for the off-card general resident 68K decoder compiler gate."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_compile_probe import (
    SaturnMidi68KResidentDecoderCompileProbeError,
    probe_saturn_midi_68k_resident_decoder_compile,
    saturn_midi_68k_resident_decoder_compile_flags,
)


def _fake_saturn_root(root: Path) -> Path:
    saturn = root / "Saturn-Dev"
    compiler = saturn / "SH_ELF" / "sh-elf" / "bin" / "sh-elf-gcc.exe"
    compiler.parent.mkdir(parents=True)
    compiler.write_bytes(b"fake-gcc")
    return saturn


class SaturnMidi68KResidentDecoderCompileProbeTests(unittest.TestCase):
    def test_compile_flags_match_standalone_c_policy(self):
        self.assertEqual(
            saturn_midi_68k_resident_decoder_compile_flags(),
            (
                "-Wall",
                "-Werror",
                "-m2",
                "-O0",
                "-ffreestanding",
                "-fno-builtin",
            ),
        )

    def test_successful_probe_generates_compile_only_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"
            calls = []

            def runner(argv, **kwargs):
                calls.append((tuple(argv), dict(kwargs)))
                object_path = Path(argv[argv.index("-o") + 1])
                object_path.write_bytes(b"SH-ELF-RESIDENT-DECODER-OBJECT")
                return SimpleNamespace(returncode=0, stdout=b"")

            result = probe_saturn_midi_68k_resident_decoder_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertTrue(result.successful)
            self.assertTrue(result.source_path.is_file())
            self.assertTrue(result.header_path.is_file())
            self.assertTrue(result.object_path.is_file())
            self.assertEqual(len(calls), 1)
            argv, kwargs = calls[0]
            self.assertEqual(argv[1], "-c")
            self.assertIn("srk_saturn_midi_68k_resident_decoder.c", argv[2])
            self.assertEqual(argv[3], "-o")
            for flag in saturn_midi_68k_resident_decoder_compile_flags():
                self.assertIn(flag, argv)
            self.assertTrue(any(item.startswith("-I") for item in argv))
            self.assertFalse(kwargs["shell"])
            self.assertFalse(kwargs["check"])

            image = build_srk_saturn_midi_68k_resident_decoder_image()
            header = result.header_path.read_text(encoding="utf-8")
            source = result.source_path.read_text(encoding="utf-8")
            self.assertIn(f"PROGRAM_WORD_COUNT {image.word_count}u", header)
            self.assertIn(f"PROGRAM_BYTE_SIZE {image.byte_size}u", header)
            self.assertIn("MAX_RECORDS 32u", header)
            self.assertNotIn("volatile", source)
            self.assertNotIn("0x25B00000", source)
            self.assertNotIn("0x2010001F", source)

            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["successful"])
            self.assertEqual(
                report["image"]["address"],
                SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
            )
            self.assertEqual(report["image"]["end_address"], image.end_address)
            self.assertEqual(report["image"]["word_count"], image.word_count)
            self.assertEqual(report["image"]["byte_size"], image.byte_size)
            self.assertEqual(report["image"]["max_records"], 32)
            self.assertTrue(report["image"]["content_independent"])
            self.assertEqual(report["image"]["sha256"], result.image_sha256)
            self.assertTrue(report["policy"]["python_native_orchestration"])
            self.assertFalse(report["policy"]["shell_used"])
            self.assertFalse(report["policy"]["path_mutated"])
            self.assertTrue(report["policy"]["generated_inputs_unchanged"])
            self.assertFalse(report["policy"]["linker_invoked"])
            self.assertFalse(report["policy"]["iso_builder_invoked"])
            self.assertFalse(report["policy"]["sd_writes"])
            self.assertFalse(report["policy"]["sound_ram_writes"])
            self.assertFalse(report["policy"]["scsp_mmio"])
            self.assertFalse(report["policy"]["smpc_commands"])
            self.assertFalse(report["policy"]["mc68ec000_program_installed"])
            self.assertFalse(report["policy"]["mc68ec000_execution"])

    def test_failed_compiler_preserves_generated_evidence_without_object(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            saturn = _fake_saturn_root(root)
            output = root / "probe"

            def runner(argv, **kwargs):
                return SimpleNamespace(returncode=1, stdout=b"compiler rejected resident decoder")

            result = probe_saturn_midi_68k_resident_decoder_compile(
                saturn,
                output,
                _runner=runner,
            )

            self.assertFalse(result.successful)
            self.assertIsNone(result.object_path)
            self.assertTrue(result.source_path.is_file())
            self.assertTrue(result.header_path.is_file())
            self.assertIn(
                "compiler rejected resident decoder",
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
                SaturnMidi68KResidentDecoderCompileProbeError,
                "already exists",
            ):
                probe_saturn_midi_68k_resident_decoder_compile(saturn, output)


if __name__ == "__main__":
    unittest.main()
