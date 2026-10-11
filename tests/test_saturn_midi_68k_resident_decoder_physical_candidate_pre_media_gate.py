"""Regression tests for the independent read-only R20 pre-media gate."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    build_srk_saturn_midi_68k_resident_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_binding import (
    render_resident_decoder_installer_header,
    render_resident_decoder_installer_source,
    render_resident_decoder_proof_header,
    render_resident_decoder_proof_source,
    render_resident_decoder_runtime_header,
    render_resident_decoder_runtime_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate import (
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_decoder_physical_candidate_pre_media,
)


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SHA = "2" * 64
_HEADER_SHA = "8" * 64
_OBJECT_SHA = "e" * 64
_BIN_SHA = "b" * 64
_CUE_SHA = "c" * 64


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _main_source() -> bytes:
    return (
        "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1\n"
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u\n"
        "srk_saturn_midi_68k_resident_decoder_physical_proof_begin\n"
        "srk_saturn_midi_68k_resident_decoder_physical_proof_poll\n"
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u\n"
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u\n"
        "Success: sequence=1 index=7 error=0\n"
        "telemetry.processed\n"
        "telemetry.current_record\n"
        "telemetry.decoder_ready\n"
    ).encode("utf-8")


def _candidate(root: Path):
    project = root / "r20"
    project.mkdir()
    image = build_srk_saturn_midi_68k_resident_decoder_image()
    seams = {
        "srk_saturn_midi_68k_resident_decoder_installer.c": render_resident_decoder_installer_source(),
        "srk_saturn_midi_68k_resident_decoder_installer.h": render_resident_decoder_installer_header(),
        "srk_saturn_midi_68k_resident_decoder_proof_preload.c": render_srk_saturn_midi_68k_resident_decoder_proof_preload_source(),
        "srk_saturn_midi_68k_resident_decoder_proof_preload.h": render_srk_saturn_midi_68k_resident_decoder_proof_preload_header(),
        "srk_saturn_midi_68k_resident_decoder_runtime.c": render_resident_decoder_runtime_source(),
        "srk_saturn_midi_68k_resident_decoder_runtime.h": render_resident_decoder_runtime_header(),
        "srk_saturn_midi_68k_resident_decoder_physical_proof.c": render_resident_decoder_proof_source(),
        "srk_saturn_midi_68k_resident_decoder_physical_proof.h": render_resident_decoder_proof_header(),
    }
    main = _main_source()
    menu = b'MIDI 68K Decoder Proof\n'
    runtime = (
        "resident_decoder_install_while_stopped\n"
        "proof_preload_publish\n"
        "resident_decoder_protocol_poll\n"
        "resident_decoder_physical_proof_begin\n"
    ).encode("utf-8")
    files: dict[str, bytes] = {
        "src/srk_saturn_main.c": main,
        "src/srk_diag_menu.c": menu,
        "src/srk_saturn_runtime.c": runtime,
    }
    for name, text in seams.items():
        files[f"src/{name}"] = text.encode("utf-8")
    generated = []
    for relative, data in files.items():
        path = _write(project, relative, data)
        generated.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    gate = {
        "schema": "srk.saturn.midi-68k-resident-decoder-physical-candidate-full-build-gate.v1",
        "candidate_define": "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1",
        "candidate_menu_label": "MIDI 68K Decoder Proof",
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "expected_read_sequence": 1,
        "expected_read_index": 7,
        "expected_last_error": 0,
        "proof_records": 7,
        "proof_final_time_us": 7000,
        "proof_covers_every_srkm_v1_opcode_once": True,
        "decoder_image_sha256": image.sha256,
        "candidate_main_sha256": _sha(main),
        "candidate_menu_sha256": _sha(menu),
        "runtime_after_sha256": _sha(runtime),
        "decoder_linked": True,
        "decoder_installed_during_build": False,
        "decoder_executed_during_build": False,
        "decoder_candidate_bound": True,
        "midi_scsp_note_attempted": False,
        "build_time_smpc_commands": False,
        "build_time_sound_ram_writes": False,
        "build_time_mc68ec000_execution": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
        "seam_sha256": {name: _sha(text.encode("utf-8")) for name, text in seams.items()},
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "sd_writes": False,
            "midi_68k_resident_decoder_present": True,
            "midi_68k_resident_decoder_linked": True,
            "midi_68k_resident_decoder_installed": False,
            "midi_68k_resident_decoder_executed": False,
            "midi_68k_resident_decoder_candidate_bound": True,
            "midi_68k_resident_decoder_user_trigger_required": True,
            "midi_68k_resident_decoder_build_time_hardware_actions": False,
            "midi_sound_ram_writes": False,
            "midi_scsp_mmio": False,
            "midi_smpc_commands": False,
            "midi_mc68ec000_execution": False,
        },
        "midi_68k_resident_decoder_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-decoder-full-build-gate.v1",
            "image_sha256": image.sha256,
            "source_sha256": _SOURCE_SHA,
            "header_sha256": _HEADER_SHA,
            "accepted_compile_object_sha256_evidence": _OBJECT_SHA,
        },
        "midi_68k_resident_decoder_physical_candidate_full_build_gate": gate,
        "generated_files": generated,
    }
    manifest_path = project / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = _sha(manifest_path.read_bytes())
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [],
    }
    report_path = project / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project, image.sha256


def _plan(root: Path):
    return SimpleNamespace(
        card_root=root / "CARD",
        category_directory=root / "CARD/saroo/ISO/TEST",
        destination_directory=root / "CARD/saroo/ISO/TEST/SRK-Diagnostics-R20",
        source_bin=root / "r20/build/SRK-Diagnostics/SRK-Diagnostics.bin",
        source_cue=root / "r20/build/SRK-Diagnostics/SRK-Diagnostics.cue",
        bin_size=225792,
        cue_size=81,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
        sector_count=96,
        raw_bytes=225792,
    )


class SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaTests(unittest.TestCase):
    def test_accepts_exact_candidate_and_read_only_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_pre_media_gate.plan_saroo_standalone_image_deployment",
                return_value=_plan(root),
            ) as planner:
                result = inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=image_sha,
                    expected_compiler_source_sha256=_SOURCE_SHA,
                    expected_compiler_header_sha256=_HEADER_SHA,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R20",
                    category="TEST",
                )
            self.assertEqual(result.proof_records, 7)
            self.assertEqual(result.proof_final_time_us, 7000)
            self.assertEqual(result.image_sha256, image_sha)
            self.assertEqual(len(result.seam_sha256), 8)
            planner.assert_called_once()

    def test_rejects_changed_compiler_or_decoder_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            with self.assertRaisesRegex(
                SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
                "provenance mismatch",
            ):
                inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=image_sha,
                    expected_compiler_source_sha256="0" * 64,
                    expected_compiler_header_sha256=_HEADER_SHA,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R20",
                    category="TEST",
                )

    def test_rejects_tampered_generated_seam(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            seam = project / "src/srk_saturn_midi_68k_resident_decoder_runtime.c"
            seam.write_text(seam.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
                "generated input changed",
            ):
                inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=image_sha,
                    expected_compiler_source_sha256=_SOURCE_SHA,
                    expected_compiler_header_sha256=_HEADER_SHA,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R20",
                    category="TEST",
                )

    def test_rejects_changed_seven_record_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            manifest_path = project / "SRK_STANDALONE_PROJECT.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["midi_68k_resident_decoder_physical_candidate_full_build_gate"]["expected_read_index"] = 27
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
                "contract mismatch: expected_read_index",
            ):
                inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
                    project,
                    root / "CARD",
                    expected_image_sha256=image_sha,
                    expected_compiler_source_sha256=_SOURCE_SHA,
                    expected_compiler_header_sha256=_HEADER_SHA,
                    expected_compiler_object_sha256=_OBJECT_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R20",
                    category="TEST",
                )

    def test_rejects_unaccepted_media_hash_and_has_no_apply_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_pre_media_gate.plan_saroo_standalone_image_deployment",
                return_value=_plan(root),
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
                    "externally accepted R20 build output",
                ):
                    inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
                        project,
                        root / "CARD",
                        expected_image_sha256=image_sha,
                        expected_compiler_source_sha256=_SOURCE_SHA,
                        expected_compiler_header_sha256=_HEADER_SHA,
                        expected_compiler_object_sha256=_OBJECT_SHA,
                        expected_bin_sha256="0" * 64,
                        expected_cue_sha256=_CUE_SHA,
                        destination_name="SRK-Diagnostics-R20",
                        category="TEST",
                    )
        source = (
            _ROOT
            / "src/rikai_kotoba/hardware/saturn/midi_68k_resident_decoder_physical_candidate_pre_media_gate.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("--apply", source)
        self.assertNotIn("deploy_saroo_standalone", source)
        self.assertNotIn("shutil.copy", source)


if __name__ == "__main__":
    unittest.main()
