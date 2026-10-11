"""Regression tests for the inert full-build integration of the resident decoder."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_decoder_image,
    render_srk_saturn_midi_68k_resident_decoder_header,
    render_srk_saturn_midi_68k_resident_decoder_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_full_build_gate import (
    SaturnMidi68KResidentDecoderFullBuildGateError,
    prepare_midi_68k_resident_decoder_full_build_gate,
)


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_OBJECT_SHA = "e" * 64


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _accepted_r19_candidate(root: Path) -> tuple[Path, str, str, str, str]:
    baseline = root / "r19-candidate"
    baseline.mkdir()
    files = {
        "src/srk_saturn_main.c": (
            b"#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1\n"
            b"R19 MIDI / 68K BATCH PROOF index 27\n"
        ),
        "src/srk_diag_menu.c": b"R19 MIDI 68K Batch Proof menu\n",
        "src/srk_saturn_runtime.c": b"accepted R19 runtime\n",
        "src/srk_saturn_midi_68k_silent_batch_program.c": b"accepted R19 batch program\n",
        "src/srk_saturn_midi_68k_silent_batch_program.h": b"accepted R19 batch header\n",
        "src/srk_saturn_midi_68k_silent_batch_installer.c": b"accepted R19 installer source\n",
        "src/srk_saturn_midi_68k_silent_batch_installer.h": b"accepted R19 installer header\n",
        "src/srk_saturn_midi_68k_silent_batch_runtime.c": b"accepted R19 batch runtime source\n",
        "src/srk_saturn_midi_68k_silent_batch_runtime.h": b"accepted R19 batch runtime header\n",
        "src/srk_saturn_midi_68k_physical_proof.h": b"accepted R19 proof header\n",
        "srk_saturn.ld": b"SECTIONS { .text 0x06004000 : { *(.text*) } }\n",
        "IP.BIN": b"IP-BIN-FIXTURE\n",
        "cd/SRKPCM.BIN": b"SRKP-FIXTURE\n",
        "build.bat": b"@echo off\r\n",
    }
    generated = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        generated.append(
            {"path": relative, "size": path.stat().st_size, "sha256": _sha(data)}
        )

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "source_trees_read_only": True,
            "sd_writes": False,
            "midi_68k_silent_batch_program_present": True,
            "midi_68k_silent_batch_program_linked": True,
            "midi_68k_silent_batch_program_installed": False,
            "midi_68k_silent_batch_program_executed": False,
            "midi_68k_silent_batch_candidate_bound": True,
            "midi_68k_silent_batch_user_trigger_required": True,
            "midi_68k_silent_batch_build_time_hardware_actions": False,
            "midi_sound_ram_writes": False,
            "midi_scsp_mmio": False,
            "midi_smpc_commands": False,
            "midi_mc68ec000_execution": False,
        },
        "midi_68k_silent_batch_physical_candidate_full_build_gate": {
            "schema": "srk.saturn.midi-68k-silent-batch-physical-candidate-full-build-gate.v1",
            "candidate_define": "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1",
            "candidate_menu_label": "MIDI 68K Batch Proof",
            "expected_read_sequence": 1,
            "expected_read_index": 27,
            "expected_last_error": 0,
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "batch_program_linked": True,
            "batch_program_installed_during_build": False,
            "batch_program_executed_during_build": False,
            "batch_candidate_bound": True,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active_when_deployed_and_explicitly_triggered": True,
        },
        "generated_files": generated,
    }
    manifest_path = baseline / _MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = _sha(manifest_path.read_bytes())

    bin_data = b"R19-ACCEPTED-BIN\n"
    cue_data = b'FILE "SRK-Diagnostics.bin" BINARY\r\n  TRACK 01 MODE1/2352\r\n'
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.bin", bin_data)
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.cue", cue_data)
    bin_sha = _sha(bin_data)
    cue_sha = _sha(cue_data)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "size": len(bin_data),
                "sha256": bin_sha,
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "size": len(cue_data),
                "sha256": cue_sha,
            },
        ],
    }
    report_path = baseline / _REPORT
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return baseline, manifest_sha, _sha(report_path.read_bytes()), bin_sha, cue_sha


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _prepare(root: Path, output_name: str = "decoder-full-build"):
    baseline, manifest_sha, report_sha, bin_sha, cue_sha = _accepted_r19_candidate(root)
    image = build_srk_saturn_midi_68k_resident_decoder_image()
    source_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8"))
    header_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8"))
    result = prepare_midi_68k_resident_decoder_full_build_gate(
        baseline,
        root / output_name,
        expected_baseline_manifest_sha256=manifest_sha,
        expected_baseline_report_sha256=report_sha,
        expected_baseline_bin_sha256=bin_sha,
        expected_baseline_cue_sha256=cue_sha,
        expected_image_sha256=image.sha256,
        expected_compiler_source_sha256=source_sha,
        expected_compiler_header_sha256=header_sha,
        expected_compiler_object_sha256=_OBJECT_SHA,
    )
    return baseline, result


class SaturnMidi68KResidentDecoderFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_inert_decoder_tree_without_mutating_r19(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha, bin_sha, cue_sha = _accepted_r19_candidate(root)
            before = _snapshot(baseline)
            image = build_srk_saturn_midi_68k_resident_decoder_image()
            source_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8"))
            header_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8"))
            output = root / "decoder-full-build"

            result = prepare_midi_68k_resident_decoder_full_build_gate(
                baseline,
                output,
                expected_baseline_manifest_sha256=manifest_sha,
                expected_baseline_report_sha256=report_sha,
                expected_baseline_bin_sha256=bin_sha,
                expected_baseline_cue_sha256=cue_sha,
                expected_image_sha256=image.sha256,
                expected_compiler_source_sha256=source_sha,
                expected_compiler_header_sha256=header_sha,
                expected_compiler_object_sha256=_OBJECT_SHA,
            )

            self.assertEqual(_snapshot(baseline), before)
            self.assertFalse((output / _REPORT).exists())
            self.assertEqual(result.image_sha256, image.sha256)
            self.assertEqual(result.image_word_count, 239)
            self.assertEqual(result.image_byte_size, 478)
            self.assertEqual(result.program_address, SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS)
            self.assertEqual(result.program_end_address, 0x000041DE)
            self.assertEqual(result.max_records, 32)

            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("accepted R19 runtime", runtime)
            self.assertIn("SRK MIDI 68K RESIDENT DECODER INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_68k_resident_decoder_program", runtime)
            self.assertEqual(
                (output / "src/srk_saturn_main.c").read_bytes(),
                (baseline / "src/srk_saturn_main.c").read_bytes(),
            )
            self.assertEqual(
                (output / "src/srk_diag_menu.c").read_bytes(),
                (baseline / "src/srk_diag_menu.c").read_bytes(),
            )

    def test_manifest_locks_linked_but_uninstalled_decoder_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, result = _prepare(root)
            manifest = json.loads((result.output_root / _MANIFEST).read_text(encoding="utf-8"))
            gate = manifest["midi_68k_resident_decoder_full_build_gate"]
            self.assertTrue(gate["existing_r19_candidate_binding_preserved"])
            self.assertEqual(gate["image_sha256"], result.image_sha256)
            self.assertEqual(gate["image_word_count"], 239)
            self.assertEqual(gate["image_byte_size"], 478)
            self.assertEqual(gate["program_address"], 0x00004000)
            self.assertEqual(gate["program_end_address"], 0x000041DE)
            self.assertEqual(gate["runtime_record_minimum"], 1)
            self.assertEqual(gate["runtime_record_maximum"], 32)
            self.assertEqual(gate["embedded_records"], 0)
            self.assertEqual(gate["accepted_compile_object_sha256_evidence"], _OBJECT_SHA)
            self.assertTrue(gate["decoder_linked"])
            self.assertFalse(gate["decoder_installed"])
            self.assertFalse(gate["decoder_executed"])
            self.assertFalse(gate["decoder_candidate_bound"])
            self.assertFalse(gate["midi_scsp_note_attempted"])
            self.assertFalse(gate["build_time_smpc_commands"])
            self.assertFalse(gate["build_time_sound_ram_writes"])
            self.assertFalse(gate["build_time_mc68ec000_execution"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])
            self.assertFalse(gate["behaviorally_active"])

            policy = manifest["policy"]
            self.assertTrue(policy["midi_68k_resident_decoder_present"])
            self.assertTrue(policy["midi_68k_resident_decoder_linked"])
            self.assertFalse(policy["midi_68k_resident_decoder_installed"])
            self.assertFalse(policy["midi_68k_resident_decoder_executed"])
            self.assertFalse(policy["midi_68k_resident_decoder_candidate_bound"])
            self.assertFalse(policy["midi_scsp_mmio"])
            self.assertFalse(policy["midi_sound_ram_writes"])
            self.assertFalse(policy["midi_mc68ec000_execution"])

    def test_inventory_pins_compiler_accepted_decoder_and_injected_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, result = _prepare(root)
            manifest = json.loads((result.output_root / _MANIFEST).read_text(encoding="utf-8"))
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                "src/srk_saturn_runtime.c",
                "src/srk_saturn_midi_68k_resident_decoder.c",
                "src/srk_saturn_midi_68k_resident_decoder.h",
            ):
                path = result.output_root / relative
                self.assertTrue(path.is_file())
                self.assertIn(relative, inventory)
                self.assertEqual(inventory[relative]["size"], path.stat().st_size)
                self.assertEqual(inventory[relative]["sha256"], _sha(path.read_bytes()))
            self.assertEqual(result.source_sha256, inventory["src/srk_saturn_midi_68k_resident_decoder.c"]["sha256"])
            self.assertEqual(result.header_sha256, inventory["src/srk_saturn_midi_68k_resident_decoder.h"]["sha256"])

    def test_refuses_provenance_mismatch_tamper_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha, bin_sha, cue_sha = _accepted_r19_candidate(root)
            image = build_srk_saturn_midi_68k_resident_decoder_image()
            source_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8"))
            header_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8"))

            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderFullBuildGateError, "manifest hash mismatch"):
                prepare_midi_68k_resident_decoder_full_build_gate(
                    baseline,
                    root / "out-a",
                    expected_baseline_manifest_sha256="0" * 64,
                    expected_baseline_report_sha256=report_sha,
                    expected_baseline_bin_sha256=bin_sha,
                    expected_baseline_cue_sha256=cue_sha,
                    expected_image_sha256=image.sha256,
                    expected_compiler_source_sha256=source_sha,
                    expected_compiler_header_sha256=header_sha,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                )
            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderFullBuildGateError, "image hash mismatch"):
                prepare_midi_68k_resident_decoder_full_build_gate(
                    baseline,
                    root / "out-b",
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_baseline_bin_sha256=bin_sha,
                    expected_baseline_cue_sha256=cue_sha,
                    expected_image_sha256="1" * 64,
                    expected_compiler_source_sha256=source_sha,
                    expected_compiler_header_sha256=header_sha,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                )
            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderFullBuildGateError, "source no longer matches"):
                prepare_midi_68k_resident_decoder_full_build_gate(
                    baseline,
                    root / "out-c",
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_baseline_bin_sha256=bin_sha,
                    expected_baseline_cue_sha256=cue_sha,
                    expected_image_sha256=image.sha256,
                    expected_compiler_source_sha256="2" * 64,
                    expected_compiler_header_sha256=header_sha,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha, bin_sha, cue_sha = _accepted_r19_candidate(root)
            (baseline / "src/srk_saturn_runtime.c").write_text("tampered\n", encoding="utf-8")
            image = build_srk_saturn_midi_68k_resident_decoder_image()
            source_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8"))
            header_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8"))
            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderFullBuildGateError, "size mismatch|hash mismatch"):
                prepare_midi_68k_resident_decoder_full_build_gate(
                    baseline,
                    root / "out-d",
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_baseline_bin_sha256=bin_sha,
                    expected_baseline_cue_sha256=cue_sha,
                    expected_image_sha256=image.sha256,
                    expected_compiler_source_sha256=source_sha,
                    expected_compiler_header_sha256=header_sha,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha, bin_sha, cue_sha = _accepted_r19_candidate(root)
            output = root / "out-e"
            output.mkdir()
            image = build_srk_saturn_midi_68k_resident_decoder_image()
            source_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8"))
            header_sha = _sha(render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8"))
            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderFullBuildGateError, "already exists"):
                prepare_midi_68k_resident_decoder_full_build_gate(
                    baseline,
                    output,
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_baseline_bin_sha256=bin_sha,
                    expected_baseline_cue_sha256=cue_sha,
                    expected_image_sha256=image.sha256,
                    expected_compiler_source_sha256=source_sha,
                    expected_compiler_header_sha256=header_sha,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                )

    def test_gate_has_no_card_or_deployment_dependency(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/rikai_kotoba/hardware/saturn/midi_68k_resident_decoder_full_build_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("standalone_image_deployment", source)
        self.assertNotIn("saroo_deployment", source)
        self.assertNotIn("card_root", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)
        self.assertNotIn("DEPLOY-", source)


if __name__ == "__main__":
    unittest.main()
