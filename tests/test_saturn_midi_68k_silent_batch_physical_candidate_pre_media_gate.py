"""Regression tests for the independent R19 silent-batch pre-media gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_pre_media_gate import (
    SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_silent_batch_physical_candidate_pre_media,
)


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_IMAGE_SHA = "d" * 64
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
        b"#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1\n"
        b"#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u\n"
        b"void f(void) {\n"
        b"  srk_saturn_midi_68k_silent_batch_physical_proof_begin(&srk_midi_68k_proof);\n"
        b"  srk_saturn_midi_68k_silent_batch_physical_proof_poll(&srk_midi_68k_proof);\n"
        b"  if((srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u){}\n"
        b"  if((srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u){}\n"
        b"  x(\"Success: sequence=1 index=27 error=0\");\n"
        b"}\n"
    )
    menu = b'const char *label = "MIDI 68K Batch Proof";\n'
    runtime = (
        b"srk_saturn_midi_68k_silent_batch_install_while_stopped\n"
        b"srk_saturn_midi_68k_silent_batch_protocol_begin\n"
        b"srk_saturn_midi_68k_silent_batch_protocol_poll\n"
        b"srk_saturn_midi_68k_silent_batch_physical_proof_reset\n"
    )
    files = {
        "src/srk_saturn_main.c": main,
        "src/srk_diag_menu.c": menu,
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_silent_batch_installer.c": b"installer source\n",
        "src/srk_saturn_midi_68k_silent_batch_installer.h": b"installer header\n",
        "src/srk_saturn_midi_68k_silent_batch_runtime.c": b"batch runtime source\n",
        "src/srk_saturn_midi_68k_silent_batch_runtime.h": b"batch runtime header\n",
        "src/srk_saturn_midi_68k_physical_proof.h": b"proof header\n",
    }
    entries = []
    for relative, data in files.items():
        path = _write(project, relative, data)
        entries.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    candidate_gate = {
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
        "candidate_main_sha256": _sha(main),
        "candidate_menu_sha256": _sha(menu),
        "installer_source_sha256": _sha(files["src/srk_saturn_midi_68k_silent_batch_installer.c"]),
        "installer_header_sha256": _sha(files["src/srk_saturn_midi_68k_silent_batch_installer.h"]),
        "batch_runtime_source_sha256": _sha(files["src/srk_saturn_midi_68k_silent_batch_runtime.c"]),
        "batch_runtime_header_sha256": _sha(files["src/srk_saturn_midi_68k_silent_batch_runtime.h"]),
        "proof_header_sha256": _sha(files["src/srk_saturn_midi_68k_physical_proof.h"]),
        "runtime_after_sha256": _sha(runtime),
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
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
        "generated_files": entries,
        "midi_68k_silent_batch_full_build_gate": {
            "schema": "srk.saturn.midi-68k-silent-batch-full-build-gate.v1",
            "image_sha256": _IMAGE_SHA,
            "expected_records": 27,
        },
        "midi_68k_silent_batch_physical_candidate_full_build_gate": candidate_gate,
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
        category_directory=Path("CARD/SAROO/ISO/TEST"),
        destination_directory=Path("CARD/SAROO/ISO/TEST/SRK-Diagnostics-R19"),
        source_bin=project / "build/SRK-Diagnostics/SRK-Diagnostics.bin",
        source_cue=project / "build/SRK-Diagnostics/SRK-Diagnostics.cue",
        source_iso=project / "build/srk_diag.iso",
        bin_size=225792,
        cue_size=81,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
        sector_count=96,
        raw_bytes=225792,
    )


class SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateTests(unittest.TestCase):
    def test_reopens_r19_candidate_and_accepts_external_image_bin_cue_anchors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _candidate(Path(temp_dir))
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=_plan(project),
            ) as planner:
                result = inspect_midi_68k_silent_batch_physical_candidate_pre_media(
                    project,
                    Path(temp_dir) / "CARD",
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

            self.assertEqual(result.image_sha256, _IMAGE_SHA)
            self.assertEqual(result.deployable_bin_sha256, _BIN_SHA)
            self.assertEqual(result.deployable_cue_sha256, _CUE_SHA)
            self.assertEqual(result.plan.destination_directory.name, "SRK-Diagnostics-R19")
            planner.assert_called_once()

    def test_rejects_tampered_manifest_pinned_runtime_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _candidate(root)
            (project / "src/srk_saturn_runtime.c").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
                "size mismatch|hash mismatch",
            ):
                inspect_midi_68k_silent_batch_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

    def test_rejects_changed_image_or_r19_pass_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project = _candidate(root)
            with self.assertRaisesRegex(
                SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
                "image hash",
            ):
                inspect_midi_68k_silent_batch_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256="a" * 64,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

            manifest_path = project / _MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["midi_68k_silent_batch_physical_candidate_full_build_gate"]["expected_read_index"] = 1
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
                "build report does not match|contract mismatch",
            ):
                inspect_midi_68k_silent_batch_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

    def test_rejects_read_only_plan_when_bin_or_cue_differs_from_external_acceptance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _candidate(Path(temp_dir))
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=_plan(project),
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
                    "BIN SHA-256",
                ):
                    inspect_midi_68k_silent_batch_physical_candidate_pre_media(
                        project,
                        Path(temp_dir) / "CARD",
                        expected_image_sha256=_IMAGE_SHA,
                        expected_bin_sha256="a" * 64,
                        expected_cue_sha256=_CUE_SHA,
                        destination_name="SRK-Diagnostics-R19",
                        category="TEST",
                    )

    def test_gate_has_no_apply_or_card_write_dependency(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "src/rikai_kotoba/hardware/saturn/"
            "midi_68k_silent_batch_physical_candidate_pre_media_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("apply_saroo_standalone_image_deployment", source)
        self.assertNotIn("CONFIRMATION_TOKEN", source)
        self.assertNotIn("--apply", source)
        self.assertNotIn("shutil.copyfile", source)


if __name__ == "__main__":
    unittest.main()
