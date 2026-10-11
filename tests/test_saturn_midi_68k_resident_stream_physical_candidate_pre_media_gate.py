"""Regression tests for the independent read-only R22 pre-media gate."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate import (
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    render_srk_saturn_midi_68k_stream_physical_proof_header,
    render_srk_saturn_midi_68k_stream_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_stream_physical_candidate_pre_media,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)


_RESIDENT_SOURCE_SHA = sha256(
    render_srk_saturn_midi_68k_resident_stream_service_source().encode("utf-8")
).hexdigest()
_RESIDENT_HEADER_SHA = sha256(
    render_srk_saturn_midi_68k_resident_stream_service_header().encode("utf-8")
).hexdigest()
_PRODUCER_SOURCE_SHA = sha256(
    render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
).hexdigest()
_PRODUCER_HEADER_SHA = sha256(
    render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
).hexdigest()
_RESIDENT_OBJECT_SHA = "a" * 64
_PRODUCER_OBJECT_SHA = "b" * 64
_BIN_SHA = "c" * 64
_CUE_SHA = "d" * 64


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _candidate(root: Path):
    project = root / "r22"
    project.mkdir()
    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    proof_header = render_srk_saturn_midi_68k_stream_physical_proof_header().encode("utf-8")
    proof_source = render_srk_saturn_midi_68k_stream_physical_proof_source().encode("utf-8")
    main = (
        "#define SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE 1\n"
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 8u\n"
        "srk_saturn_midi_68k_stream_physical_proof_begin\n"
        "srk_saturn_midi_68k_stream_physical_proof_poll\n"
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u\n"
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u\n"
        "Stream PASS: refill + timing + state\n"
        "wait_zero_pass\npartial_15ms_pass\nbatch1_ack_pass\n"
        "refill_wait_pass\nbatch2_ack_pass\nfinal_cc74\n"
        "srk_midi_68k_draw_field(2, 26, 36, \"Release A to arm proof action\");\n"
        "srk_midi_68k_draw_field(2, 27, 36, \"START Return to diagnostics menu\");\n"
    ).encode("utf-8")
    menu = b"MIDI 68K Stream Proof\n"
    runtime = (
        "srk_saturn_midi_stream_clock_publish(0UL)\n"
        "srk_saturn_midi_stream_clock_publish(15000UL)\n"
        "srk_saturn_midi_stream_clock_publish(32000UL)\n"
        "srk_saturn_midi_stream_clock_publish(40000UL)\n"
        "srk_saturn_midi_stream_batch_publish\n"
        "expected_summary_words\nexpected_controller_words\nexpected_active_words\n"
    ).encode("utf-8")
    files = {
        "src/srk_saturn_main.c": main,
        "src/srk_diag_menu.c": menu,
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_stream_physical_proof.h": proof_header,
        "src/srk_saturn_midi_68k_stream_physical_proof.c": proof_source,
    }
    generated = []
    for relative, data in files.items():
        path = _write(project, relative, data)
        generated.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    snapshot = asdict(build_srk_saturn_midi_68k_stream_physical_snapshot())
    gate = {
        "schema": "srk.saturn.midi-68k-resident-stream-physical-candidate-full-build-gate.v1",
        "candidate_define": "#define SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE 1",
        "candidate_menu_label": "MIDI 68K Stream Proof",
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "proof_records": 40,
        "batch1_records": 32,
        "batch2_records": 8,
        "partial_clock_us": 15000,
        "batch1_clock_us": 32000,
        "final_clock_us": 40000,
        "expected_final_read_sequence": 2,
        "expected_final_read_index": 8,
        "expected_final_batch_count": 2,
        "expected_total_records": 40,
        "wait_zero_required": True,
        "partial_15ms_exactly_15_required": True,
        "batch1_ack_required": True,
        "refill_wait_at_old_clock_required": True,
        "batch2_ack_required": True,
        "persistent_state_required": True,
        "state_summary_words_verified": 256,
        "controller_words_verified": 1024,
        "active_note_words_verified": 128,
        "expected_state_snapshot": snapshot,
        "image_sha256": image.sha256,
        "candidate_main_sha256": _sha(main),
        "candidate_menu_sha256": _sha(menu),
        "runtime_after_sha256": _sha(runtime),
        "proof_header_sha256": _sha(proof_header),
        "proof_source_sha256": _sha(proof_source),
        "resident_stream_linked": True,
        "resident_stream_installed_during_build": False,
        "resident_stream_executed_during_build": False,
        "resident_stream_candidate_bound": True,
        "producer_linked": True,
        "producer_invoked_during_build": False,
        "midi_scsp_note_attempted": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
    }
    inert = {
        "schema": "srk.saturn.midi-68k-resident-stream-full-build-gate.v1",
        "image_sha256": image.sha256,
        "resident_source_sha256": _RESIDENT_SOURCE_SHA,
        "resident_header_sha256": _RESIDENT_HEADER_SHA,
        "producer_source_sha256": _PRODUCER_SOURCE_SHA,
        "producer_header_sha256": _PRODUCER_HEADER_SHA,
        "accepted_resident_object_sha256_evidence": _RESIDENT_OBJECT_SHA,
        "accepted_producer_object_sha256_evidence": _PRODUCER_OBJECT_SHA,
        "multi_batch_refill": True,
        "strict_sequence_service": True,
        "timestamp_scheduler": True,
        "published_clock_seqlock": True,
        "state_persistent_across_refills": True,
        "resident_stream_linked": True,
        "resident_stream_installed": False,
        "resident_stream_executed": False,
        "producer_linked": True,
        "producer_invoked": False,
        "midi_scsp_note_attempted": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {
            "sd_writes": False,
            "midi_68k_resident_stream_present": True,
            "midi_68k_resident_stream_linked": True,
            "midi_68k_resident_stream_installed": False,
            "midi_68k_resident_stream_executed": False,
            "midi_68k_resident_stream_candidate_bound": True,
            "midi_68k_stream_producer_linked": True,
            "midi_68k_stream_producer_invoked": False,
            "midi_sound_ram_writes": False,
            "midi_scsp_mmio": False,
            "midi_smpc_commands": False,
            "midi_mc68ec000_execution": False,
        },
        "midi_68k_resident_stream_full_build_gate": inert,
        "midi_68k_resident_stream_physical_candidate_full_build_gate": gate,
        "generated_files": generated,
    }
    manifest_path = project / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = _sha(manifest_path.read_bytes())
    (project / "SRK_STANDALONE_BUILD.json").write_text(
        json.dumps(
            {
                "schema": "srk.saturn.standalone-build.v1",
                "successful": True,
                "project_manifest_sha256": manifest_sha,
                "artifacts": [],
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    return project, image.sha256


def _plan(root: Path):
    return SimpleNamespace(
        card_root=root / "CARD",
        category_directory=root / "CARD/saroo/ISO/TEST",
        destination_directory=root / "CARD/saroo/ISO/TEST/SRK-Diagnostics-R22",
        source_bin=root / "r22/build/SRK-Diagnostics/SRK-Diagnostics.bin",
        source_cue=root / "r22/build/SRK-Diagnostics/SRK-Diagnostics.cue",
        bin_size=263424,
        cue_size=81,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
        sector_count=112,
        raw_bytes=263424,
    )


def _kwargs(image_sha: str) -> dict[str, str]:
    return {
        "expected_image_sha256": image_sha,
        "expected_resident_source_sha256": _RESIDENT_SOURCE_SHA,
        "expected_resident_header_sha256": _RESIDENT_HEADER_SHA,
        "expected_producer_source_sha256": _PRODUCER_SOURCE_SHA,
        "expected_producer_header_sha256": _PRODUCER_HEADER_SHA,
        "expected_resident_object_sha256": _RESIDENT_OBJECT_SHA,
        "expected_producer_object_sha256": _PRODUCER_OBJECT_SHA,
        "expected_bin_sha256": _BIN_SHA,
        "expected_cue_sha256": _CUE_SHA,
        "destination_name": "SRK-Diagnostics-R22",
        "category": "TEST",
    }


class SaturnMidi68KResidentStreamPhysicalCandidatePreMediaTests(unittest.TestCase):
    def test_accepts_r22_and_read_only_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_pre_media_gate.plan_saroo_standalone_image_deployment",
                return_value=_plan(root),
            ) as planner:
                result = inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                    project, root / "CARD", **_kwargs(image_sha)
                )
            self.assertEqual((result.proof_records, result.batch1_records, result.batch2_records), (40, 32, 8))
            self.assertEqual(
                (
                    result.clock_zero_us,
                    result.clock_partial_us,
                    result.clock_batch1_us,
                    result.clock_final_us,
                ),
                (0, 15000, 32000, 40000),
            )
            self.assertEqual(
                (
                    result.summary_words_verified,
                    result.controller_words_verified,
                    result.active_note_words_verified,
                ),
                (256, 1024, 128),
            )
            planner.assert_called_once()

    def test_rejects_changed_compiler_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            args = _kwargs(image_sha)
            args["expected_resident_source_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
                "provenance mismatch",
            ):
                inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                    project, root / "CARD", **args
                )

    def test_rejects_tampered_proof_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            source = project / "src/srk_saturn_midi_68k_stream_physical_proof.c"
            source.write_text(source.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
                "generated input changed",
            ):
                inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                    project, root / "CARD", **_kwargs(image_sha)
                )

    def test_rejects_changed_timing_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            manifest_path = project / "SRK_STANDALONE_PROJECT.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["midi_68k_resident_stream_physical_candidate_full_build_gate"][
                "partial_clock_us"
            ] = 14999
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
                "contract mismatch: partial_clock_us",
            ):
                inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                    project, root / "CARD", **_kwargs(image_sha)
                )

    def test_rejects_unaccepted_media_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project, image_sha = _candidate(root)
            args = _kwargs(image_sha)
            args["expected_bin_sha256"] = "0" * 64
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_pre_media_gate.plan_saroo_standalone_image_deployment",
                return_value=_plan(root),
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
                    "externally accepted build output",
                ):
                    inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                        project, root / "CARD", **args
                    )


if __name__ == "__main__":
    unittest.main()
