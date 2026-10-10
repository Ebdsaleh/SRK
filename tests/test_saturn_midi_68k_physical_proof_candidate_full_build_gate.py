"""Regression tests for the callable-but-off-card MIDI/68K proof candidate gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof_candidate_full_build_gate import (
    SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
    prepare_midi_68k_physical_proof_candidate_full_build_gate,
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


def _physical_proof_baseline(root: Path, *, successful: bool = True) -> Path:
    baseline = root / "physical-proof-baseline"
    baseline.mkdir()
    files = {
        "src/srk_saturn_main.c": b"old inert main\n",
        "src/srk_diag_menu.c": b"old inert menu\n",
        "src/srk_saturn_runtime.c": (
            b"/* SRK MIDI 68K PHYSICAL PROOF INERT FULL-BUILD GATE: controller follows. */\n"
            b"unsigned int srk_saturn_midi_68k_physical_proof_begin(void *state) { return 5u; }\n"
        ),
        "src/srk_saturn_midi_68k_physical_proof.c": b"physical proof source\n",
        "src/srk_saturn_midi_68k_physical_proof.h": b"physical proof header\n",
        "srk_saturn.ld": b"SECTIONS { .text 0x06004000 : { *(.text*) } }\n",
        "IP.BIN": b"IP-BIN-FIXTURE\n",
        "cd/SRKPCM.BIN": b"SRKP-FIXTURE\n",
        "build.bat": b"@echo off\r\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha(data),
            }
        )

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "source_trees_read_only": True,
            "sd_writes": False,
            "midi_68k_physical_proof_linked": True,
            "midi_68k_physical_proof_called": False,
            "midi_68k_runtime_called": False,
            "midi_68k_hardware_adapter_called": False,
            "midi_68k_program_installed": False,
            "midi_68k_reset_vectors_changed": False,
            "midi_sound_ram_writes": False,
            "midi_scsp_mmio": False,
            "midi_smpc_commands": False,
            "midi_mc68ec000_execution": False,
        },
        "midi_68k_physical_proof_full_build_gate": {
            "schema": "srk.saturn.midi-68k-physical-proof-full-build-gate.v1",
            "proof_linked": True,
            "proof_called": False,
            "adapter_linked": True,
            "adapter_called": False,
            "runtime_called": False,
            "installer_called": False,
            "program_installed": False,
            "reset_vectors_changed": False,
            "producer_called": False,
            "smpc_commands_executed": False,
            "sound_ram_runtime_writes": False,
            "mc68ec000_execution": False,
            "behaviorally_active": False,
        },
        "generated_files": entries,
    }
    manifest_path = baseline / _MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": successful,
        "project_manifest_sha256": _sha(manifest_path.read_bytes()),
    }
    (baseline / _REPORT).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return baseline


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class SaturnMidi68KPhysicalProofCandidateFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_callable_candidate_without_mutating_accepted_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _physical_proof_baseline(root)
            before = _snapshot(baseline)
            output = root / "candidate"

            result = prepare_midi_68k_physical_proof_candidate_full_build_gate(
                baseline,
                output,
            )

            self.assertEqual(_snapshot(baseline), before)
            self.assertEqual(result.baseline_root, baseline.resolve())
            self.assertEqual(result.output_root, output.resolve())
            self.assertFalse((output / _REPORT).exists())

            main = (output / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (output / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            self.assertTrue(
                main.startswith("#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1\n")
            )
            self.assertIn("srk_saturn_midi_68k_physical_proof_begin", main)
            self.assertIn("srk_saturn_midi_68k_physical_proof_poll", main)
            self.assertIn('"MIDI 68K Silent Proof"', menu)
            self.assertNotIn('"Timing / Interrupt Test"', menu)

    def test_candidate_manifest_records_explicit_trigger_and_zero_build_time_hardware_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "candidate"
            prepare_midi_68k_physical_proof_candidate_full_build_gate(
                _physical_proof_baseline(root),
                output,
            )

            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            gate = manifest["midi_68k_physical_proof_candidate_full_build_gate"]
            self.assertTrue(gate["proof_linked"])
            self.assertTrue(gate["proof_ui_compiled"])
            self.assertTrue(gate["proof_call_path_compiled"])
            self.assertFalse(gate["proof_called_during_build"])
            self.assertTrue(gate["user_trigger_required"])
            self.assertEqual(gate["trigger_button"], "A")
            self.assertTrue(gate["trigger_requires_release_after_screen_entry"])
            self.assertEqual(gate["poll_mode"], "at-most-once-per-frame-while-running")
            self.assertEqual(gate["success_read_sequence"], 1)
            self.assertEqual(gate["success_read_index"], 1)
            self.assertEqual(gate["success_last_error"], 0)
            self.assertFalse(gate["midi_scsp_note_attempted"])
            self.assertFalse(gate["build_time_smpc_commands"])
            self.assertFalse(gate["build_time_sound_ram_writes"])
            self.assertFalse(gate["build_time_mc68ec000_execution"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])
            self.assertTrue(
                gate["behaviorally_active_when_deployed_and_explicitly_triggered"]
            )

            policy = manifest["policy"]
            self.assertFalse(policy["sd_writes"])
            self.assertTrue(policy["midi_68k_physical_proof_candidate_bound"])
            self.assertTrue(policy["midi_68k_physical_proof_user_trigger_required"])
            self.assertFalse(policy["midi_68k_candidate_build_time_hardware_actions"])
            self.assertFalse(policy["midi_smpc_commands"])
            self.assertFalse(policy["midi_sound_ram_writes"])
            self.assertFalse(policy["midi_mc68ec000_execution"])

    def test_candidate_inventory_pins_replaced_binding_and_preserves_physical_proof_inputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "candidate"
            prepare_midi_68k_physical_proof_candidate_full_build_gate(
                _physical_proof_baseline(root),
                output,
            )

            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                "src/srk_saturn_main.c",
                "src/srk_diag_menu.c",
                "src/srk_saturn_runtime.c",
                "src/srk_saturn_midi_68k_physical_proof.c",
                "src/srk_saturn_midi_68k_physical_proof.h",
            ):
                path = output / relative
                self.assertTrue(path.is_file())
                self.assertIn(relative, inventory)
                self.assertEqual(inventory[relative]["size"], path.stat().st_size)
                self.assertEqual(inventory[relative]["sha256"], _sha(path.read_bytes()))

    def test_refuses_nonphysical_unsuccessful_tampered_or_existing_baselines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _physical_proof_baseline(root, successful=False)
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
                "was not successful",
            ):
                prepare_midi_68k_physical_proof_candidate_full_build_gate(
                    baseline,
                    root / "candidate-a",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _physical_proof_baseline(root)
            manifest_path = baseline / _MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("midi_68k_physical_proof_full_build_gate")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            report = json.loads((baseline / _REPORT).read_text(encoding="utf-8"))
            report["project_manifest_sha256"] = _sha(manifest_path.read_bytes())
            (baseline / _REPORT).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
                "not an inert MIDI 68K physical-proof",
            ):
                prepare_midi_68k_physical_proof_candidate_full_build_gate(
                    baseline,
                    root / "candidate-b",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _physical_proof_baseline(root)
            (baseline / "src/srk_saturn_runtime.c").write_text(
                "tampered\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
                "size mismatch|hash mismatch",
            ):
                prepare_midi_68k_physical_proof_candidate_full_build_gate(
                    baseline,
                    root / "candidate-c",
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _physical_proof_baseline(root)
            output = root / "candidate-d"
            output.mkdir()
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
                "already exists",
            ):
                prepare_midi_68k_physical_proof_candidate_full_build_gate(
                    baseline,
                    output,
                )

    def test_gate_has_no_card_or_deployment_dependency(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/rikai_kotoba/hardware/saturn/"
            "midi_68k_physical_proof_candidate_full_build_gate.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("standalone_image_deployment", source)
        self.assertNotIn("saroo_deployment", source)
        self.assertNotIn("card_root", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
