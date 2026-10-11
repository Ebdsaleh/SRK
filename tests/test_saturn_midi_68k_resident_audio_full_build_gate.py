"""Regression tests for the R23 resident-audio inert full-build gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_full_build_gate import (
    SaturnMidi68KResidentAudioFullBuildGateError,
    prepare_midi_68k_resident_audio_full_build_gate,
    run_midi_68k_resident_audio_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    build_srk_saturn_midi_68k_resident_audio_service_image,
    render_srk_saturn_midi_68k_resident_audio_service_header,
    render_srk_saturn_midi_68k_resident_audio_service_source,
    render_srk_saturn_midi_68k_resident_audio_voice_header,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate import (
    render_srk_saturn_midi_68k_stream_physical_proof_header,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a import (
    render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _baseline(root: Path) -> dict[str, str]:
    deploy = root / "build" / "SRK-Diagnostics"
    deploy.mkdir(parents=True)

    proof_source = render_srk_saturn_midi_68k_stream_physical_proof_source_r22a().encode("utf-8")
    proof_header = render_srk_saturn_midi_68k_stream_physical_proof_header().encode("utf-8")
    producer_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    producer_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
    files = {
        "src/srk_saturn_main.c": b"/* r22a main */\n",
        "src/srk_diag_menu.c": b"/* r22a menu */\n",
        "src/srk_saturn_runtime.c": b"/* r22a runtime with callable proof */\n",
        "src/srk_saturn_midi_68k_stream_physical_proof.c": proof_source,
        "src/srk_saturn_midi_68k_stream_physical_proof.h": proof_header,
        "src/srk_saturn_midi_68k_stream_service.c": producer_source,
        "src/srk_saturn_midi_68k_stream_service.h": producer_header,
    }
    for relative, payload in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    bin_path = deploy / "SRK-Diagnostics.bin"
    cue_path = deploy / "SRK-Diagnostics.cue"
    bin_path.write_bytes(b"R22A-BIN")
    cue_path.write_bytes(b"R22A-CUE")

    main_sha = _file_sha(root / "src/srk_saturn_main.c")
    menu_sha = _file_sha(root / "src/srk_diag_menu.c")
    runtime_sha = _file_sha(root / "src/srk_saturn_runtime.c")
    proof_source_sha = _sha(proof_source)
    proof_header_sha = _sha(proof_header)

    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_resident_stream_physical_candidate_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-stream-physical-candidate-full-build-gate.v1",
            "candidate_menu_label": "MIDI 68K Stream Proof",
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
            "resident_stream_candidate_bound": True,
            "producer_linked": True,
            "producer_invoked_during_build": False,
            "midi_scsp_note_attempted": False,
            "build_time_hardware_io": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active_when_deployed_and_explicitly_triggered": True,
            "candidate_main_sha256": main_sha,
            "candidate_menu_sha256": menu_sha,
            "runtime_after_sha256": runtime_sha,
            "proof_source_sha256": proof_source_sha,
            "proof_header_sha256": proof_header_sha,
        },
        "generated_files": [
            {"path": relative, "size": len(payload), "sha256": _sha(payload)}
            for relative, payload in files.items()
        ],
    }
    manifest_path = root / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha = _file_sha(manifest_path)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.bin", "sha256": _file_sha(bin_path)},
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.cue", "sha256": _file_sha(cue_path)},
        ],
    }
    report_path = root / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": manifest_sha,
        "report": _file_sha(report_path),
        "bin": _file_sha(bin_path),
        "cue": _file_sha(cue_path),
        "runtime": runtime_sha,
        "main": main_sha,
        "menu": menu_sha,
        "proof_source": proof_source_sha,
        "proof_header": proof_header_sha,
        "producer_source": _sha(producer_source),
        "producer_header": _sha(producer_header),
    }


def _kwargs(hashes: dict[str, str]) -> dict[str, str]:
    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    return {
        "expected_baseline_manifest_sha256": hashes["manifest"],
        "expected_baseline_report_sha256": hashes["report"],
        "expected_baseline_bin_sha256": hashes["bin"],
        "expected_baseline_cue_sha256": hashes["cue"],
        "expected_baseline_runtime_sha256": hashes["runtime"],
        "expected_baseline_main_sha256": hashes["main"],
        "expected_baseline_menu_sha256": hashes["menu"],
        "expected_baseline_proof_source_sha256": hashes["proof_source"],
        "expected_baseline_proof_header_sha256": hashes["proof_header"],
        "expected_image_sha256": image.sha256,
        "expected_resident_source_sha256": _sha(render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")),
        "expected_resident_header_sha256": _sha(render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")),
        "expected_voice_header_sha256": _sha(render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")),
        "expected_producer_source_sha256": hashes["producer_source"],
        "expected_producer_header_sha256": hashes["producer_header"],
        "expected_resident_object_sha256": "1" * 64,
        "expected_producer_object_sha256": "2" * 64,
    }


class SaturnMidi68KResidentAudioFullBuildGateTests(unittest.TestCase):
    def test_prepare_preserves_r22a_binding_and_adds_only_inert_audio_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r22a"
            baseline.mkdir()
            hashes = _baseline(baseline)
            output = root / "r23-inert"
            prepared = prepare_midi_68k_resident_audio_full_build_gate(
                baseline, output, **_kwargs(hashes)
            )

            self.assertEqual(_file_sha(output / "src/srk_saturn_main.c"), hashes["main"])
            self.assertEqual(_file_sha(output / "src/srk_diag_menu.c"), hashes["menu"])
            self.assertEqual(prepared.runtime_before_sha256, hashes["runtime"])
            self.assertNotEqual(prepared.runtime_after_sha256, hashes["runtime"])
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("R23 AUDIO INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_68k_resident_audio_service_program", runtime)
            self.assertNotIn("srk_saturn_midi_68k_resident_audio_install", runtime)

            self.assertTrue((output / "src/srk_saturn_midi_68k_resident_audio_service.c").is_file())
            self.assertTrue((output / "src/srk_saturn_midi_68k_voice_state.h").is_file())
            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_resident_audio_full_build_gate"]
            self.assertTrue(gate["existing_r22a_candidate_binding_preserved"])
            self.assertEqual(gate["voice_allocator"], "slot-0-monophonic-no-steal")
            self.assertTrue(gate["midi_scsp_image_capable"])
            self.assertFalse(gate["resident_audio_installed"])
            self.assertFalse(gate["resident_audio_executed"])
            self.assertFalse(gate["resident_audio_candidate_bound"])
            self.assertFalse(gate["midi_scsp_note_attempted_during_build"])
            self.assertFalse(gate["build_time_hardware_io"])
            self.assertFalse(gate["saroo_write"])

    def test_existing_output_is_rejected_without_touching_r22a(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r22a"
            baseline.mkdir()
            hashes = _baseline(baseline)
            before = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(
                SaturnMidi68KResidentAudioFullBuildGateError, "already exists"
            ):
                prepare_midi_68k_resident_audio_full_build_gate(
                    baseline, output, **_kwargs(hashes)
                )
            after = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_wrong_accepted_r22a_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r22a"
            baseline.mkdir()
            hashes = _baseline(baseline)
            kwargs = _kwargs(hashes)
            kwargs["expected_baseline_bin_sha256"] = "f" * 64
            with self.assertRaisesRegex(
                SaturnMidi68KResidentAudioFullBuildGateError, "R22A BIN"
            ):
                prepare_midi_68k_resident_audio_full_build_gate(
                    baseline, root / "out", **kwargs
                )

    def test_wrong_r23_compiler_representation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r22a"
            baseline.mkdir()
            hashes = _baseline(baseline)
            kwargs = _kwargs(hashes)
            kwargs["expected_voice_header_sha256"] = "e" * 64
            with self.assertRaisesRegex(
                SaturnMidi68KResidentAudioFullBuildGateError,
                "generated representation",
            ):
                prepare_midi_68k_resident_audio_full_build_gate(
                    baseline, root / "out", **kwargs
                )

    def test_run_invokes_normal_standalone_builder_after_prepare(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r22a"
            baseline.mkdir()
            hashes = _baseline(baseline)
            fake_build = SimpleNamespace(successful=True)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_audio_full_build_gate."
                "build_saturn_standalone_project",
                return_value=fake_build,
            ) as builder:
                result = run_midi_68k_resident_audio_full_build_gate(
                    baseline, root / "out", **_kwargs(hashes)
                )
            self.assertIs(result.build, fake_build)
            builder.assert_called_once_with(result.prepared.output_root)


if __name__ == "__main__":
    unittest.main()
