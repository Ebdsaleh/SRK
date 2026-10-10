"""Regression tests for the callable silent 27-record MIDI/68K candidate gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_full_build_gate import (
    SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError,
    prepare_midi_68k_silent_batch_physical_candidate_full_build_gate,
)


_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_IMAGE_SHA = "a" * 64
_BIN = b"accepted-inert-bin"
_CUE = b'FILE "SRK-Diagnostics.bin" BINARY\n'


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _baseline(root: Path) -> Path:
    baseline = root / "inert-batch"
    baseline.mkdir()
    files = {
        "src/srk_saturn_main.c": b"accepted R18 main\n",
        "src/srk_diag_menu.c": b"accepted R18 menu\n",
        "src/srk_saturn_runtime.c": b"accepted R18 runtime plus inert batch image\n",
        "src/srk_saturn_midi_68k_silent_batch_program.c": b"batch const data\n",
        "src/srk_saturn_midi_68k_silent_batch_program.h": b"batch const header\n",
        "srk_saturn.ld": b"SECTIONS { .text 0x06004000 : { *(.text*) } }\n",
        "IP.BIN": b"IP-BIN-FIXTURE\n",
        "cd/SRKPCM.BIN": b"SRKP-FIXTURE\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_silent_batch_full_build_gate": {
            "schema": "srk.saturn.midi-68k-silent-batch-full-build-gate.v1",
            "image_sha256": _IMAGE_SHA,
            "existing_r18_candidate_binding_preserved": True,
            "batch_program_linked": True,
            "batch_program_installed": False,
            "batch_program_executed": False,
            "batch_candidate_bound": False,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
        },
        "generated_files": entries,
    }
    manifest_path = baseline / _MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    bin_path = _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.bin", _BIN)
    cue_path = _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.cue", _CUE)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": _sha(manifest_path.read_bytes()),
        "artifacts": [
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.bin", "size": bin_path.stat().st_size, "sha256": _sha(_BIN)},
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.cue", "size": cue_path.stat().st_size, "sha256": _sha(_CUE)},
        ],
    }
    (baseline / _REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return baseline


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _prepare(baseline: Path, output: Path):
    return prepare_midi_68k_silent_batch_physical_candidate_full_build_gate(
        baseline,
        output,
        expected_image_sha256=_IMAGE_SHA,
        expected_deploy_bin_sha256=_sha(_BIN),
        expected_deploy_cue_sha256=_sha(_CUE),
    )


class SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateTests(unittest.TestCase):
    def test_derives_fresh_callable_candidate_without_mutating_inert_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            before = _snapshot(baseline)
            output = root / "candidate"
            result = _prepare(baseline, output)

            self.assertEqual(_snapshot(baseline), before)
            self.assertEqual(result.baseline_root, baseline.resolve())
            self.assertEqual(result.output_root, output.resolve())
            self.assertFalse((output / _REPORT).exists())
            main = (output / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (output / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            self.assertTrue(main.startswith("#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1\n"))
            self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u", main)
            self.assertIn('"MIDI 68K Batch Proof"', menu)

    def test_manifest_locks_explicit_trigger_and_zero_build_time_hardware_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "candidate"
            _prepare(_baseline(root), output)
            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            gate = manifest["midi_68k_silent_batch_physical_candidate_full_build_gate"]
            self.assertEqual(gate["expected_read_sequence"], 1)
            self.assertEqual(gate["expected_read_index"], 27)
            self.assertEqual(gate["expected_last_error"], 0)
            self.assertTrue(gate["trigger_requires_release_after_screen_entry"])
            self.assertTrue(gate["batch_candidate_bound"])
            self.assertFalse(gate["batch_program_installed_during_build"])
            self.assertFalse(gate["batch_program_executed_during_build"])
            self.assertFalse(gate["midi_scsp_note_attempted"])
            self.assertFalse(gate["build_time_smpc_commands"])
            self.assertFalse(gate["build_time_sound_ram_writes"])
            self.assertFalse(gate["build_time_mc68ec000_execution"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])

    def test_inventory_pins_candidate_binding_and_runtime_seams(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "candidate"
            result = _prepare(_baseline(root), output)
            manifest = json.loads((output / _MANIFEST).read_text(encoding="utf-8"))
            inventory = {entry["path"]: entry for entry in manifest["generated_files"]}
            for relative in (
                "src/srk_saturn_main.c",
                "src/srk_diag_menu.c",
                "src/srk_saturn_runtime.c",
                "src/srk_saturn_midi_68k_silent_batch_installer.c",
                "src/srk_saturn_midi_68k_silent_batch_installer.h",
                "src/srk_saturn_midi_68k_silent_batch_runtime.c",
                "src/srk_saturn_midi_68k_silent_batch_runtime.h",
                "src/srk_saturn_midi_68k_physical_proof.h",
            ):
                path = output / relative
                self.assertTrue(path.is_file())
                self.assertEqual(inventory[relative]["sha256"], _sha(path.read_bytes()))
            self.assertEqual(result.runtime_after_sha256, inventory["src/srk_saturn_runtime.c"]["sha256"])

    def test_rejects_hash_mismatch_tampering_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError, "different silent-batch image"):
                prepare_midi_68k_silent_batch_physical_candidate_full_build_gate(
                    baseline,
                    root / "a",
                    expected_image_sha256="b" * 64,
                    expected_deploy_bin_sha256=_sha(_BIN),
                    expected_deploy_cue_sha256=_sha(_CUE),
                )

            with self.assertRaisesRegex(SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError, "BIN hash"):
                prepare_midi_68k_silent_batch_physical_candidate_full_build_gate(
                    baseline,
                    root / "b",
                    expected_image_sha256=_IMAGE_SHA,
                    expected_deploy_bin_sha256="c" * 64,
                    expected_deploy_cue_sha256=_sha(_CUE),
                )

            (baseline / "src/srk_saturn_runtime.c").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError, "size mismatch|hash mismatch"):
                _prepare(baseline, root / "c")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = _baseline(root)
            output = root / "candidate"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError, "already exists"):
                _prepare(baseline, output)

    def test_gate_has_no_card_or_deployment_dependency(self):
        source = (
            _ROOT
            / "src/rikai_kotoba/hardware/saturn/"
            "midi_68k_silent_batch_physical_candidate_full_build_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("standalone_image_deployment", source)
        self.assertNotIn("saroo_deployment", source)
        self.assertNotIn("card_root", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
