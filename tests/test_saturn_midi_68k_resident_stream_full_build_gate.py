"""Regression tests for the continuous stream-service inert full-build gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_full_build_gate import (
    SaturnMidi68KResidentStreamFullBuildGateError,
    prepare_midi_68k_resident_stream_full_build_gate,
    run_midi_68k_resident_stream_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
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
    src = root / "src"
    deploy = root / "build" / "SRK-Diagnostics"
    src.mkdir(parents=True)
    deploy.mkdir(parents=True)
    files = {
        "src/srk_saturn_main.c": b"/* r21 main */\n",
        "src/srk_diag_menu.c": b"/* r21 menu */\n",
        "src/srk_saturn_runtime.c": b"/* r21 runtime */\n",
        "src/srk_saturn_midi_generated.h": b"/* generated */\n",
        "src/srk_saturn_midi_mailbox.h": b"/* mailbox */\n",
    }
    for relative, payload in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    bin_path = deploy / "SRK-Diagnostics.bin"
    cue_path = deploy / "SRK-Diagnostics.cue"
    bin_path.write_bytes(b"R21-BIN")
    cue_path.write_bytes(b"R21-CUE")

    main_sha = _file_sha(root / "src/srk_saturn_main.c")
    menu_sha = _file_sha(root / "src/srk_diag_menu.c")
    runtime_sha = _file_sha(root / "src/srk_saturn_runtime.c")
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_resident_state_decoder_physical_candidate_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-state-decoder-physical-candidate-full-build-gate.v1",
            "candidate_menu_label": "MIDI 68K State Proof",
            "expected_read_sequence": 1,
            "expected_read_index": 20,
            "expected_last_error": 0,
            "proof_records": 20,
            "proof_final_time_us": 20000,
            "proof_covers_every_srkm_v1_opcode": True,
            "state_verification_required": True,
            "state_summary_words_verified": 256,
            "controller_words_verified": 1024,
            "active_note_words_verified": 128,
            "state_decoder_candidate_bound": True,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "candidate_main_sha256": main_sha,
            "candidate_menu_sha256": menu_sha,
            "runtime_after_sha256": runtime_sha,
        },
        "generated_files": [
            {
                "path": relative,
                "size": len(payload),
                "sha256": _sha(payload),
            }
            for relative, payload in files.items()
        ],
    }
    manifest_path = root / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = _file_sha(manifest_path)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "sha256": _file_sha(bin_path),
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "sha256": _file_sha(cue_path),
            },
        ],
    }
    report_path = root / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "manifest": manifest_sha,
        "report": _file_sha(report_path),
        "bin": _file_sha(bin_path),
        "cue": _file_sha(cue_path),
        "runtime": runtime_sha,
        "main": main_sha,
        "menu": menu_sha,
    }


def _kwargs(hashes: dict[str, str]) -> dict[str, str]:
    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    return {
        "expected_baseline_manifest_sha256": hashes["manifest"],
        "expected_baseline_report_sha256": hashes["report"],
        "expected_baseline_bin_sha256": hashes["bin"],
        "expected_baseline_cue_sha256": hashes["cue"],
        "expected_baseline_runtime_sha256": hashes["runtime"],
        "expected_image_sha256": image.sha256,
        "expected_resident_source_sha256": _sha(render_srk_saturn_midi_68k_resident_stream_service_source().encode("utf-8")),
        "expected_resident_header_sha256": _sha(render_srk_saturn_midi_68k_resident_stream_service_header().encode("utf-8")),
        "expected_producer_source_sha256": _sha(render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")),
        "expected_producer_header_sha256": _sha(render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")),
        "expected_resident_object_sha256": "1" * 64,
        "expected_producer_object_sha256": "2" * 64,
    }


class SaturnMidi68KResidentStreamFullBuildGateTests(unittest.TestCase):
    def test_prepare_preserves_r21_binding_and_adds_only_inert_service_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r21"
            baseline.mkdir()
            hashes = _baseline(baseline)
            output = root / "stream-inert"
            prepared = prepare_midi_68k_resident_stream_full_build_gate(
                baseline,
                output,
                **_kwargs(hashes),
            )

            self.assertEqual(_file_sha(output / "src/srk_saturn_main.c"), hashes["main"])
            self.assertEqual(_file_sha(output / "src/srk_diag_menu.c"), hashes["menu"])
            self.assertEqual(prepared.runtime_before_sha256, hashes["runtime"])
            self.assertNotEqual(prepared.runtime_after_sha256, hashes["runtime"])
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("RESIDENT STREAM INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_68k_resident_stream_service_program", runtime)
            self.assertIn("srk_saturn_midi_stream_clock_publish", runtime)

            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_resident_stream_full_build_gate"]
            self.assertTrue(gate["existing_r21_candidate_binding_preserved"])
            self.assertTrue(gate["multi_batch_refill"])
            self.assertTrue(gate["timestamp_scheduler"])
            self.assertTrue(gate["published_clock_seqlock"])
            self.assertTrue(gate["state_persistent_across_refills"])
            self.assertFalse(gate["resident_stream_installed"])
            self.assertFalse(gate["resident_stream_executed"])
            self.assertFalse(gate["producer_invoked"])
            self.assertFalse(gate["saroo_write"])

    def test_existing_output_is_rejected_without_touching_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r21"
            baseline.mkdir()
            hashes = _baseline(baseline)
            before = {path.relative_to(baseline): path.read_bytes() for path in baseline.rglob("*") if path.is_file()}
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KResidentStreamFullBuildGateError, "already exists"):
                prepare_midi_68k_resident_stream_full_build_gate(
                    baseline,
                    output,
                    **_kwargs(hashes),
                )
            after = {path.relative_to(baseline): path.read_bytes() for path in baseline.rglob("*") if path.is_file()}
            self.assertEqual(after, before)

    def test_wrong_physical_r21_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r21"
            baseline.mkdir()
            hashes = _baseline(baseline)
            kwargs = _kwargs(hashes)
            kwargs["expected_baseline_bin_sha256"] = "f" * 64
            with self.assertRaisesRegex(SaturnMidi68KResidentStreamFullBuildGateError, "R21 BIN"):
                prepare_midi_68k_resident_stream_full_build_gate(
                    baseline,
                    root / "out",
                    **kwargs,
                )

    def test_run_invokes_normal_standalone_builder_after_prepare(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r21"
            baseline.mkdir()
            hashes = _baseline(baseline)
            fake_build = SimpleNamespace(successful=True)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_full_build_gate."
                "build_saturn_standalone_project",
                return_value=fake_build,
            ) as builder:
                result = run_midi_68k_resident_stream_full_build_gate(
                    baseline,
                    root / "out",
                    **_kwargs(hashes),
                )
            self.assertIs(result.build, fake_build)
            builder.assert_called_once_with(result.prepared.output_root)


if __name__ == "__main__":
    unittest.main()
