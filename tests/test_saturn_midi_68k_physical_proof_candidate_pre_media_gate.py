"""Regression tests for the independent R18 MIDI/68K pre-media gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof_candidate_pre_media_gate import (
    SaturnMidi68KPhysicalProofCandidatePreMediaGateError,
    inspect_midi_68k_physical_proof_candidate_pre_media,
)


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_BIN_SHA = "8" * 64
_CUE_SHA = "5" * 64


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _candidate(root: Path) -> Path:
    project = root / "candidate"
    project.mkdir()
    main = (
        b"#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1\n"
        b"void f(void) {\n"
        b"  srk_saturn_midi_68k_physical_proof_begin(&srk_midi_68k_proof);\n"
        b"  srk_saturn_midi_68k_physical_proof_poll(&srk_midi_68k_proof);\n"
        b"  if((srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u){}\n"
        b"  if((srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u){}\n"
        b"  x(\"Success: sequence=1 index=1 error=0\");\n"
        b"}\n"
    )
    menu = b'const char *label = "MIDI 68K Silent Proof";\n'
    proof_source = b"physical proof source\n"
    proof_header = b"physical proof header\n"
    files = {
        "src/srk_saturn_main.c": main,
        "src/srk_diag_menu.c": menu,
        "src/srk_saturn_midi_68k_physical_proof.c": proof_source,
        "src/srk_saturn_midi_68k_physical_proof.h": proof_header,
        "src/srk_saturn_runtime.c": b"runtime\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(project, relative, data)
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    gate = {
        "schema": "srk.saturn.midi-68k-physical-proof-candidate-full-build-gate.v1",
        "candidate_define": "#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1",
        "candidate_main": "src/srk_saturn_main.c",
        "candidate_menu": "src/srk_diag_menu.c",
        "candidate_menu_label": "MIDI 68K Silent Proof",
        "proof_linked": True,
        "proof_ui_compiled": True,
        "proof_call_path_compiled": True,
        "proof_called_during_build": False,
        "user_trigger_required": True,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
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
        "candidate_main_sha256": _sha(main),
        "candidate_menu_sha256": _sha(menu),
        "proof_source_sha256": _sha(proof_source),
        "proof_header_sha256": _sha(proof_header),
    }
    policy = {
        "sd_writes": False,
        "midi_68k_physical_proof_linked": True,
        "midi_68k_physical_proof_called": False,
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
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": policy,
        "generated_files": entries,
        "midi_68k_physical_proof_candidate_full_build_gate": gate,
    }
    manifest_path = project / _MANIFEST
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": _sha(manifest_path.read_bytes()),
    }
    (project / _REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


def _plan(project: Path):
    return SimpleNamespace(
        project_root=project,
        card_root=Path("CARD"),
        destination_directory=Path("CARD/SAROO/ISO/TEST/SRK-Diagnostics-R18"),
        source_bin=project / "build/SRK-Diagnostics/SRK-Diagnostics.bin",
        source_cue=project / "build/SRK-Diagnostics/SRK-Diagnostics.cue",
        source_iso=project / "build/srk_diag.iso",
        bin_size=188160,
        cue_size=81,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
        sector_count=80,
        raw_bytes=188160,
    )


class SaturnMidi68KPhysicalProofCandidatePreMediaGateTests(unittest.TestCase):
    def test_reopens_candidate_and_accepts_only_external_hash_anchored_read_only_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _candidate(Path(temp_dir))
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_physical_proof_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=_plan(project),
            ) as planner:
                result = inspect_midi_68k_physical_proof_candidate_pre_media(
                    project,
                    Path(temp_dir) / "CARD",
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R18",
                    category="TEST",
                )

            self.assertEqual(result.deployable_bin_sha256, _BIN_SHA)
            self.assertEqual(result.deployable_cue_sha256, _CUE_SHA)
            self.assertEqual(result.plan.destination_directory.name, "SRK-Diagnostics-R18")
            planner.assert_called_once()

    def test_rejects_tampered_manifest_pinned_candidate_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _candidate(Path(temp_dir))
            (project / "src/srk_saturn_main.c").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidatePreMediaGateError,
                "size mismatch|hash mismatch",
            ):
                inspect_midi_68k_physical_proof_candidate_pre_media(
                    project,
                    Path(temp_dir) / "CARD",
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R18",
                    category="TEST",
                )

    def test_rejects_report_not_bound_to_current_manifest_or_changed_proof_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _candidate(root)
            manifest_path = project / _MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["midi_68k_physical_proof_candidate_full_build_gate"]["user_trigger_required"] = False
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KPhysicalProofCandidatePreMediaGateError,
                "build report does not match|contract mismatch",
            ):
                inspect_midi_68k_physical_proof_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R18",
                    category="TEST",
                )

    def test_rejects_fresh_plan_when_bin_or_cue_differs_from_external_acceptance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _candidate(Path(temp_dir))
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_physical_proof_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=_plan(project),
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KPhysicalProofCandidatePreMediaGateError,
                    "BIN SHA-256",
                ):
                    inspect_midi_68k_physical_proof_candidate_pre_media(
                        project,
                        Path(temp_dir) / "CARD",
                        expected_bin_sha256="a" * 64,
                        expected_cue_sha256=_CUE_SHA,
                        destination_name="SRK-Diagnostics-R18",
                        category="TEST",
                    )

    def test_gate_has_no_apply_or_card_write_dependency(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/rikai_kotoba/hardware/saturn/"
            "midi_68k_physical_proof_candidate_pre_media_gate.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("apply_saroo_standalone_image_deployment", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)
        self.assertNotIn("--apply", source)
        self.assertNotIn("shutil.copyfile", source)


if __name__ == "__main__":
    unittest.main()
