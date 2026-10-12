"""Regression contracts for the R24 complete-song legacy compiler gate."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_r24_compile_probe import (
    SaturnMidi68KR24CompileProbeError,
    probe_saturn_midi_68k_r24_compile,
    saturn_midi_68k_r24_compile_flags,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    SATURN_MIDI_68K_R24_REFERENCE_SHA256,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


class SaturnMidi68KR24CompileProbeTests(unittest.TestCase):
    def test_compile_policy_matches_existing_legacy_flags(self):
        self.assertEqual(
            saturn_midi_68k_r24_compile_flags(),
            ("-Wall", "-Werror", "-m2", "-O0", "-ffreestanding", "-fno-builtin"),
        )

    def test_existing_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KR24CompileProbeError, "already exists"):
                probe_saturn_midi_68k_r24_compile(root, _REFERENCE, output)

    def test_mock_compile_builds_four_objects_and_records_real_song_policy(self):
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
                "rikai_kotoba.hardware.saturn.midi_68k_r24_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_r24_compile(
                    root,
                    _REFERENCE,
                    output,
                    _runner=runner,
                )

            self.assertTrue(result.successful)
            self.assertEqual(len(calls), 4)
            self.assertEqual(result.source_midi_sha256, SATURN_MIDI_68K_R24_REFERENCE_SHA256)
            self.assertEqual(
                result.image_sha256,
                build_srk_saturn_midi_68k_r24_resident_audio_service_image().sha256,
            )
            self.assertEqual(len(result.object_sha256), 4)
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "srk.saturn.midi-68k-r24-compile-probe.v1")
            self.assertEqual(report["source_midi"]["records"], 310)
            self.assertEqual(report["source_midi"]["batches"], 10)
            self.assertEqual(report["source_midi"]["batch_sizes"], [32] * 9 + [22])
            self.assertEqual(report["source_midi"]["peak_polyphony"], 2)
            self.assertEqual(
                report["resident_image"]["voice_allocator"],
                "slots0-1-lowest-free-no-steal",
            )
            self.assertTrue(report["resident_image"]["calibrated_pitch_table"])
            self.assertTrue(report["resident_image"]["velocity_mixer_table"])
            self.assertFalse(report["policy"]["sd_writes"])
            self.assertFalse(report["policy"]["scsp_mmio_executed"])
            self.assertFalse(report["policy"]["frt_mmio_executed"])
            self.assertFalse(report["policy"]["physical_clock_frequency_selected"])

    def test_failed_compile_records_failure_without_fabricating_objects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compiler = root / "sh-elf-gcc.exe"
            compiler.write_bytes(b"fake")
            output = root / "gate"
            environment = SimpleNamespace(
                compiler=SimpleNamespace(path_for=lambda _name: compiler)
            )
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_compile_probe."
                "inspect_saturn_standalone_environment",
                return_value=environment,
            ):
                result = probe_saturn_midi_68k_r24_compile(
                    root,
                    _REFERENCE,
                    output,
                    _runner=lambda *_args, **_kwargs: SimpleNamespace(
                        returncode=1,
                        stdout=b"compile failed",
                    ),
                )
            self.assertFalse(result.successful)
            self.assertEqual(result.object_sha256, ())
            self.assertIn("compile failed", result.log_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
