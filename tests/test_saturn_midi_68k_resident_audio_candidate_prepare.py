"""Regression tests for deriving the fresh R23 physical candidate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate as _physical
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_candidate_prepare import (
    SaturnMidi68KResidentAudioCandidatePrepareError,
    prepare_midi_68k_resident_audio_physical_candidate,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_full_build_gate import (
    run_midi_68k_resident_audio_physical_candidate_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    build_srk_saturn_midi_68k_resident_audio_service_image,
    render_srk_saturn_midi_68k_resident_audio_service_header,
    render_srk_saturn_midi_68k_resident_audio_service_source,
    render_srk_saturn_midi_68k_resident_audio_voice_header,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_OWNED_SLOTS,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(path.read_bytes())


def _synthetic_stream_main() -> str:
    stream_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_stream_physical_proof.h"',
            "#endif",
        )
    )
    stream_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 8u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K STREAM PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "32+8 refill - timestamp scheduler"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Stream PASS: refill + timing + state"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_stream_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_stream_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_stream_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    stream_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    return "\n".join(
        (
            _physical._STREAM_DEFINE,
            _physical._STREAM_GUARD,
            _physical._STREAM_GUARD,
            stream_include,
            stream_alias,
            _physical._stream_telemetry_block(),
            stream_success,
            "",
        )
    )


def _baseline(root: Path) -> dict[str, str]:
    src = root / "src"
    deploy = root / "build" / "SRK-Diagnostics"
    src.mkdir(parents=True)
    deploy.mkdir(parents=True)

    resident_source = render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")
    resident_header = render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")
    voice_header = render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")
    producer_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    producer_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")

    files = {
        "src/srk_saturn_main.c": _synthetic_stream_main().encode("utf-8"),
        "src/srk_diag_menu.c": b'x\n"MIDI 68K Stream Proof"\ny\n',
        "src/srk_saturn_runtime.c": b"/* R23 inert runtime */\n",
        "src/srk_saturn_midi_68k_resident_audio_service.c": resident_source,
        "src/srk_saturn_midi_68k_resident_audio_service.h": resident_header,
        "src/srk_saturn_midi_68k_voice_state.h": voice_header,
        "src/srk_saturn_midi_68k_stream_service.c": producer_source,
        "src/srk_saturn_midi_68k_stream_service.h": producer_header,
    }
    for relative, payload in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    bin_path = deploy / "SRK-Diagnostics.bin"
    cue_path = deploy / "SRK-Diagnostics.cue"
    bin_path.write_bytes(b"R23-INERT-BIN")
    cue_path.write_bytes(b"R23-INERT-CUE")

    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    main_sha = _file_sha(root / "src/srk_saturn_main.c")
    menu_sha = _file_sha(root / "src/srk_diag_menu.c")
    runtime_sha = _file_sha(root / "src/srk_saturn_runtime.c")
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_resident_audio_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-audio-full-build-gate.v1",
            "image_sha256": image.sha256,
            "resident_source_sha256": _sha(resident_source),
            "resident_header_sha256": _sha(resident_header),
            "voice_header_sha256": _sha(voice_header),
            "producer_source_sha256": _sha(producer_source),
            "producer_header_sha256": _sha(producer_header),
            "accepted_resident_object_sha256_evidence": "1" * 64,
            "accepted_producer_object_sha256_evidence": "2" * 64,
            "existing_r22a_candidate_binding_preserved": True,
            "r22a_main_sha256": main_sha,
            "r22a_menu_sha256": menu_sha,
            "voice_allocator": "slot-0-monophonic-no-steal",
            "owned_slots": SATURN_MIDI_68K_R23_OWNED_SLOTS,
            "voice_state_address": SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
            "scsp_register_base": SATURN_MIDI_68K_SCSP_REGISTER_BASE,
            "first_note_channel": SATURN_MIDI_68K_R23_CHANNEL,
            "first_note_note": SATURN_MIDI_68K_R23_NOTE,
            "first_note_velocity": SATURN_MIDI_68K_R23_VELOCITY,
            "r22a_queue_refill_semantics_preserved": True,
            "r22a_timestamp_scheduler_preserved": True,
            "r22a_midi_state_semantics_preserved": True,
            "resident_audio_linked": True,
            "resident_audio_installed": False,
            "resident_audio_executed": False,
            "resident_audio_candidate_bound": False,
            "producer_already_linked_from_r22a": True,
            "producer_invoked_during_build": False,
            "midi_scsp_image_capable": True,
            "midi_scsp_note_attempted_during_build": False,
            "build_time_hardware_io": False,
            "runtime_after_sha256": runtime_sha,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
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
        "image": image.sha256,
        "resident_source": _sha(resident_source),
        "resident_header": _sha(resident_header),
        "voice_header": _sha(voice_header),
        "producer_source": _sha(producer_source),
        "producer_header": _sha(producer_header),
    }


def _kwargs(hashes: dict[str, str]) -> dict[str, str]:
    return {
        "expected_baseline_bin_sha256": hashes["bin"],
        "expected_baseline_cue_sha256": hashes["cue"],
        "expected_baseline_runtime_sha256": hashes["runtime"],
        "expected_image_sha256": hashes["image"],
        "expected_resident_source_sha256": hashes["resident_source"],
        "expected_resident_header_sha256": hashes["resident_header"],
        "expected_voice_header_sha256": hashes["voice_header"],
        "expected_producer_source_sha256": hashes["producer_source"],
        "expected_producer_header_sha256": hashes["producer_header"],
        "expected_resident_object_sha256": "1" * 64,
        "expected_producer_object_sha256": "2" * 64,
    }


class SaturnMidi68KResidentAudioCandidatePrepareTests(unittest.TestCase):
    def test_prepare_binds_r23_proof_without_hardware_io(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            hashes = _baseline(baseline)
            output = root / "candidate"
            prepared = prepare_midi_68k_resident_audio_physical_candidate(
                baseline,
                output,
                **_kwargs(hashes),
            )
            self.assertEqual(prepared.baseline_manifest_sha256, hashes["manifest"])
            self.assertEqual(prepared.baseline_report_sha256, hashes["report"])
            main = (output / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (output / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertTrue(main.startswith("#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1\n"))
            self.assertIn("MIDI / 68K AUDIO PROOF", main)
            self.assertIn('"MIDI 68K Audio Proof"', menu)
            self.assertIn("R23 AUDIO PHYSICAL CANDIDATE", runtime)
            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_resident_audio_physical_candidate_full_build_gate"]
            self.assertEqual(gate["proof_records"], 34)
            self.assertEqual((gate["batch1_records"], gate["batch2_records"]), (32, 2))
            self.assertTrue(gate["scsp_key_on_readback_required"])
            self.assertTrue(gate["audible_midi_note_required"])
            self.assertTrue(gate["scheduled_note_off_required"])
            self.assertTrue(gate["scsp_key_off_readback_required"])
            self.assertFalse(gate["build_time_hardware_io"])
            self.assertFalse(gate["saroo_write"])

    def test_prepare_preserves_exact_inert_compiler_anchors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            hashes = _baseline(baseline)
            prepared = prepare_midi_68k_resident_audio_physical_candidate(
                baseline,
                root / "candidate",
                **_kwargs(hashes),
            )
            self.assertEqual(prepared.image_sha256, hashes["image"])
            self.assertEqual(prepared.baseline_bin_sha256, hashes["bin"])
            self.assertEqual(prepared.baseline_cue_sha256, hashes["cue"])
            self.assertEqual((prepared.proof_records, prepared.batch1_records, prepared.batch2_records), (34, 32, 2))
            self.assertEqual(prepared.voice_words_verified, 15)

    def test_wrong_inert_bin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            hashes = _baseline(baseline)
            kwargs = _kwargs(hashes)
            kwargs["expected_baseline_bin_sha256"] = "f" * 64
            with self.assertRaisesRegex(SaturnMidi68KResidentAudioCandidatePrepareError, "R23 inert BIN"):
                prepare_midi_68k_resident_audio_physical_candidate(
                    baseline,
                    root / "out",
                    **kwargs,
                )

    def test_existing_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            hashes = _baseline(baseline)
            output = root / "exists"
            output.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KResidentAudioCandidatePrepareError, "already exists"):
                prepare_midi_68k_resident_audio_physical_candidate(
                    baseline,
                    output,
                    **_kwargs(hashes),
                )

    def test_full_build_gate_invokes_normal_builder_after_prepare(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            hashes = _baseline(baseline)
            fake_build = SimpleNamespace(successful=True)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_full_build_gate."
                "build_saturn_standalone_project",
                return_value=fake_build,
            ) as builder:
                result = run_midi_68k_resident_audio_physical_candidate_full_build_gate(
                    baseline,
                    root / "candidate",
                    **_kwargs(hashes),
                )
            self.assertIs(result.build, fake_build)
            builder.assert_called_once_with(result.prepared.output_root)


if __name__ == "__main__":
    unittest.main()
