"""Regression tests for the inert full-build integration of the silent 68K batch image."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_consumer import (
    SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_silent_batch_consumer_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_full_build_gate import (
    SaturnMidi68KSilentBatchFullBuildGateError,
    prepare_midi_68k_silent_batch_full_build_gate,
)


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _accepted_r18_candidate(root: Path) -> tuple[Path, str, str]:
    baseline = root / "r18-candidate"
    baseline.mkdir()
    files = {
        "src/srk_saturn_main.c": b"#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1\nold main\n",
        "src/srk_diag_menu.c": b"old R18 MIDI 68K Silent Proof menu\n",
        "src/srk_saturn_runtime.c": b"old R18 runtime\n",
        "src/srk_saturn_midi_68k_physical_proof.c": b"old R18 proof source\n",
        "src/srk_saturn_midi_68k_physical_proof.h": b"old R18 proof header\n",
        "srk_saturn.ld": b"SECTIONS { .text 0x06004000 : { *(.text*) } }\n",
        "IP.BIN": b"IP-BIN-FIXTURE\n",
        "cd/SRKPCM.BIN": b"SRKP-FIXTURE\n",
        "build.bat": b"@echo off\r\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        entries.append(
            {"path": relative, "size": path.stat().st_size, "sha256": _sha(data)}
        )

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "source_trees_read_only": True,
            "sd_writes": False,
            "midi_68k_physical_proof_candidate_bound": True,
            "midi_68k_physical_proof_user_trigger_required": True,
            "midi_68k_candidate_build_time_hardware_actions": False,
            "midi_68k_runtime_called": False,
            "midi_68k_hardware_adapter_called": False,
            "midi_68k_program_installed": False,
            "midi_68k_reset_vectors_changed": False,
            "midi_sound_ram_writes": False,
            "midi_scsp_mmio": False,
            "midi_smpc_commands": False,
            "midi_mc68ec000_execution": False,
        },
        "midi_68k_physical_proof_candidate_full_build_gate": {
            "schema": "srk.saturn.midi-68k-physical-proof-candidate-full-build-gate.v1",
            "proof_linked": True,
            "proof_ui_compiled": True,
            "proof_call_path_compiled": True,
            "proof_called_during_build": False,
            "user_trigger_required": True,
            "trigger_requires_release_after_screen_entry": True,
            "success_read_sequence": 1,
            "success_read_index": 1,
            "success_last_error": 0,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active_when_deployed_and_explicitly_triggered": True,
        },
        "generated_files": entries,
    }
    manifest_path = baseline / _MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = _sha(manifest_path.read_bytes())
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
    }
    report_path = baseline / _REPORT
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return baseline, manifest_sha, _sha(report_path.read_bytes())


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _prepare(root: Path, output_name: str = "batch-full-build"):
    baseline, manifest_sha, report_sha = _accepted_r18_candidate(root)
    image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
    result = prepare_midi_68k_silent_batch_full_build_gate(
        baseline,
        root / output_name,
        expected_baseline_manifest_sha256=manifest_sha,
        expected_baseline_report_sha256=report_sha,
        expected_image_sha256=image.sha256,
    )
    return baseline, result


class SaturnMidi68KSilentBatchFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_inert_batch_tree_without_mutating_r18(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha = _accepted_r18_candidate(root)
            before = _snapshot(baseline)
            image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
            output = root / "batch-full-build"

            result = prepare_midi_68k_silent_batch_full_build_gate(
                baseline,
                output,
                expected_baseline_manifest_sha256=manifest_sha,
                expected_baseline_report_sha256=report_sha,
                expected_image_sha256=image.sha256,
            )

            self.assertEqual(_snapshot(baseline), before)
            self.assertFalse((output / _REPORT).exists())
            self.assertEqual(result.image_sha256, image.sha256)
            self.assertEqual(result.image_word_count, 5066)
            self.assertEqual(result.image_byte_size, 10132)
            self.assertEqual(result.program_address, SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS)
            self.assertEqual(result.program_end_address, 0x00006794)
            self.assertEqual(result.expected_records, 27)

            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("old R18 runtime", runtime)
            self.assertIn("SRK MIDI 68K SILENT FULL-BATCH INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_68k_silent_batch_program", runtime)
            self.assertTrue((output / "src/srk_saturn_midi_68k_silent_batch_program.c").is_file())
            self.assertTrue((output / "src/srk_saturn_midi_68k_silent_batch_program.h").is_file())
            self.assertEqual(
                (output / "src/srk_saturn_main.c").read_bytes(),
                (baseline / "src/srk_saturn_main.c").read_bytes(),
            )
            self.assertEqual(
                (output / "src/srk_diag_menu.c").read_bytes(),
                (baseline / "src/srk_diag_menu.c").read_bytes(),
            )

    def test_manifest_locks_linked_but_uninstalled_unbound_batch_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, result = _prepare(root)
            manifest = json.loads((result.output_root / _MANIFEST).read_text(encoding="utf-8"))
            gate = manifest["midi_68k_silent_batch_full_build_gate"]
            self.assertTrue(gate["existing_r18_candidate_binding_preserved"])
            self.assertEqual(gate["image_sha256"], result.image_sha256)
            self.assertEqual(gate["image_word_count"], 5066)
            self.assertEqual(gate["image_byte_size"], 10132)
            self.assertEqual(gate["program_address"], 0x00004000)
            self.assertEqual(gate["program_end_address"], 0x00006794)
            self.assertEqual(gate["expected_records"], 27)
            self.assertEqual(gate["queue_word_count"], 108)
            self.assertTrue(gate["batch_program_linked"])
            self.assertFalse(gate["batch_program_installed"])
            self.assertFalse(gate["batch_program_executed"])
            self.assertFalse(gate["batch_candidate_bound"])
            self.assertFalse(gate["midi_scsp_note_attempted"])
            self.assertFalse(gate["build_time_smpc_commands"])
            self.assertFalse(gate["build_time_sound_ram_writes"])
            self.assertFalse(gate["build_time_mc68ec000_execution"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])
            self.assertFalse(gate["behaviorally_active"])

            policy = manifest["policy"]
            self.assertTrue(policy["midi_68k_silent_batch_program_present"])
            self.assertTrue(policy["midi_68k_silent_batch_program_linked"])
            self.assertFalse(policy["midi_68k_silent_batch_program_installed"])
            self.assertFalse(policy["midi_68k_silent_batch_program_executed"])
            self.assertFalse(policy["midi_68k_silent_batch_candidate_bound"])
            self.assertFalse(policy["midi_scsp_mmio"])
            self.assertFalse(policy["midi_sound_ram_writes"])
            self.assertFalse(policy["midi_mc68ec000_execution"])

    def test_inventory_pins_batch_files_and_injected_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, result = _prepare(root)
            manifest = json.loads((result.output_root / _MANIFEST).read_text(encoding="utf-8"))
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                "src/srk_saturn_runtime.c",
                "src/srk_saturn_midi_68k_silent_batch_program.c",
                "src/srk_saturn_midi_68k_silent_batch_program.h",
            ):
                path = result.output_root / relative
                self.assertTrue(path.is_file())
                self.assertIn(relative, inventory)
                self.assertEqual(inventory[relative]["size"], path.stat().st_size)
                self.assertEqual(inventory[relative]["sha256"], _sha(path.read_bytes()))

    def test_refuses_hash_mismatch_tamper_and_existing_output(self):
        image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha = _accepted_r18_candidate(root)
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchFullBuildGateError, "manifest hash mismatch"):
                prepare_midi_68k_silent_batch_full_build_gate(
                    baseline,
                    root / "out-a",
                    expected_baseline_manifest_sha256="0" * 64,
                    expected_baseline_report_sha256=report_sha,
                    expected_image_sha256=image.sha256,
                )
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchFullBuildGateError, "image hash mismatch"):
                prepare_midi_68k_silent_batch_full_build_gate(
                    baseline,
                    root / "out-b",
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_image_sha256="1" * 64,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha = _accepted_r18_candidate(root)
            (baseline / "src/srk_saturn_runtime.c").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchFullBuildGateError, "size mismatch|hash mismatch"):
                prepare_midi_68k_silent_batch_full_build_gate(
                    baseline,
                    root / "out-c",
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_image_sha256=image.sha256,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, manifest_sha, report_sha = _accepted_r18_candidate(root)
            output = root / "out-d"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchFullBuildGateError, "already exists"):
                prepare_midi_68k_silent_batch_full_build_gate(
                    baseline,
                    output,
                    expected_baseline_manifest_sha256=manifest_sha,
                    expected_baseline_report_sha256=report_sha,
                    expected_image_sha256=image.sha256,
                )

    def test_gate_has_no_card_or_deployment_dependency(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/rikai_kotoba/hardware/saturn/midi_68k_silent_batch_full_build_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("standalone_image_deployment", source)
        self.assertNotIn("saroo_deployment", source)
        self.assertNotIn("card_root", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
