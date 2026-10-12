"""Regression contracts for the R24 complete-song inert standalone gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_r24_inert_full_build_gate import (
    SaturnMidi68KR24InertFullBuildGateError,
    prepare_saturn_midi_68k_r24_inert_full_build_gate,
    run_saturn_midi_68k_r24_inert_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate import (
    render_srk_saturn_midi_68k_r23_physical_proof_header,
    render_srk_saturn_midi_68k_r23_physical_proof_source,
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


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(path.read_bytes())


def _write(root: Path, relative: str, data: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _make_r23_baseline(root: Path) -> dict[str, str]:
    main = b"/* accepted R23 main */\n"
    menu = b"/* accepted R23 menu */\n"
    runtime = b"/* accepted R23 runtime */\n"
    audio_source = render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")
    audio_header = render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")
    voice_header = render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")
    producer_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    producer_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
    proof_source = render_srk_saturn_midi_68k_r23_physical_proof_source().encode("utf-8")
    proof_header = render_srk_saturn_midi_68k_r23_physical_proof_header().encode("utf-8")

    files = {
        "src/srk_saturn_main.c": main,
        "src/srk_diag_menu.c": menu,
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_resident_audio_service.c": audio_source,
        "src/srk_saturn_midi_68k_resident_audio_service.h": audio_header,
        "src/srk_saturn_midi_68k_voice_state.h": voice_header,
        "src/srk_saturn_midi_68k_stream_service.c": producer_source,
        "src/srk_saturn_midi_68k_stream_service.h": producer_header,
        "src/srk_saturn_midi_68k_r23_physical_proof.c": proof_source,
        "src/srk_saturn_midi_68k_r23_physical_proof.h": proof_header,
        "src/srk_saturn_midi_generated.h": b"typedef struct SRK_SATURN_MIDI_EVENT { unsigned long time_us; unsigned char opcode, channel, data0, data1; } SRK_SATURN_MIDI_EVENT;\n#define SRK_MIDI_QUEUE_CAPACITY 32u\n",
        "src/srk_saturn_midi_mailbox.h": b"/* mailbox */\n",
    }
    for relative, data in files.items():
        _write(root, relative, data)

    generated = [
        {"path": relative, "size": len(data), "sha256": _sha(data)}
        for relative, data in sorted(files.items())
    ]
    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    gate = {
        "schema": "srk.saturn.midi-68k-resident-audio-physical-candidate-full-build-gate.v1",
        "candidate_menu_label": "MIDI 68K Audio Proof",
        "proof_records": 34,
        "batch1_records": 32,
        "batch2_records": 2,
        "expected_final_read_sequence": 2,
        "expected_final_read_index": 2,
        "expected_final_batch_count": 2,
        "expected_total_records": 34,
        "scsp_key_on_readback_required": True,
        "audible_midi_note_required": True,
        "scheduled_note_off_required": True,
        "scsp_key_off_readback_required": True,
        "resident_audio_candidate_bound": True,
        "producer_linked": True,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "image_sha256": image.sha256,
        "candidate_main_sha256": _sha(main),
        "candidate_menu_sha256": _sha(menu),
        "runtime_after_sha256": _sha(runtime),
        "proof_source_sha256": _sha(proof_source),
        "proof_header_sha256": _sha(proof_header),
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "generated_files": generated,
        "midi_68k_resident_audio_physical_candidate_full_build_gate": gate,
    }
    manifest_path = root / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = _sha_file(manifest_path)

    deploy_bin = b"accepted-r23-bin"
    deploy_cue = b'FILE "SRK-Diagnostics.bin" BINARY\n'
    _write(root, "build/SRK-Diagnostics/SRK-Diagnostics.bin", deploy_bin)
    _write(root, "build/SRK-Diagnostics/SRK-Diagnostics.cue", deploy_cue)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "size": len(deploy_bin),
                "sha256": _sha(deploy_bin),
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "size": len(deploy_cue),
                "sha256": _sha(deploy_cue),
            },
        ],
    }
    report_path = root / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "manifest": manifest_sha,
        "report": _sha_file(report_path),
        "bin": _sha(deploy_bin),
        "cue": _sha(deploy_cue),
        "image": image.sha256,
        "resident_source": _sha(audio_source),
        "resident_header": _sha(audio_header),
        "voice_header": _sha(voice_header),
        "producer_source": _sha(producer_source),
        "producer_header": _sha(producer_header),
        "proof_source": _sha(proof_source),
        "proof_header": _sha(proof_header),
    }


def _kwargs(values: dict[str, str]) -> dict[str, str]:
    return {
        "expected_baseline_manifest_sha256": values["manifest"],
        "expected_baseline_report_sha256": values["report"],
        "expected_baseline_bin_sha256": values["bin"],
        "expected_baseline_cue_sha256": values["cue"],
        "expected_r23_image_sha256": values["image"],
        "expected_r23_resident_source_sha256": values["resident_source"],
        "expected_r23_resident_header_sha256": values["resident_header"],
        "expected_r23_voice_header_sha256": values["voice_header"],
        "expected_r23_producer_source_sha256": values["producer_source"],
        "expected_r23_producer_header_sha256": values["producer_header"],
        "expected_r23_proof_source_sha256": values["proof_source"],
        "expected_r23_proof_header_sha256": values["proof_header"],
    }


class SaturnMidi68KR24InertFullBuildGateTests(unittest.TestCase):
    def test_prepares_fresh_inert_tree_without_mutating_r23_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r23"
            baseline.mkdir()
            values = _make_r23_baseline(baseline)
            before = {p.relative_to(baseline): p.read_bytes() for p in baseline.rglob("*") if p.is_file()}
            output = root / "r24"

            prepared = prepare_saturn_midi_68k_r24_inert_full_build_gate(
                baseline,
                _REFERENCE,
                output,
                **_kwargs(values),
            )

            after = {p.relative_to(baseline): p.read_bytes() for p in baseline.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual((output / "src/srk_saturn_main.c").read_bytes(), before[Path("src/srk_saturn_main.c")])
            self.assertEqual((output / "src/srk_diag_menu.c").read_bytes(), before[Path("src/srk_diag_menu.c")])
            self.assertEqual(prepared.song_records, 310)
            self.assertEqual(prepared.song_batches, 10)
            self.assertEqual(prepared.peak_polyphony, 2)
            self.assertNotEqual(prepared.r24_image_sha256, prepared.baseline_r23_image_sha256)
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("R24 REAL-SMF INERT FULL-BUILD GATE", runtime)
            self.assertIn("srk_saturn_midi_68k_r24_resident_audio_service_program", runtime)
            self.assertIn("srk_saturn_midi_r24_player_poll", runtime)
            self.assertIn("srk_saturn_midi_r24_frt_sample_us", runtime)

    def test_manifest_locks_inert_policy_and_real_song_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r23"
            baseline.mkdir()
            values = _make_r23_baseline(baseline)
            output = root / "r24"
            prepare_saturn_midi_68k_r24_inert_full_build_gate(
                baseline, _REFERENCE, output, **_kwargs(values)
            )
            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_r24_inert_full_build_gate"]
            self.assertEqual(gate["song_records"], 310)
            self.assertEqual(gate["song_batches"], 10)
            self.assertEqual(gate["song_batch_sizes"], [32] * 9 + [22])
            self.assertEqual(gate["peak_polyphony"], 2)
            self.assertTrue(gate["accepted_r23_candidate_binding_preserved"])
            self.assertTrue(gate["resident_linked_as_constant_data"])
            self.assertFalse(gate["resident_installed"])
            self.assertFalse(gate["resident_executed"])
            self.assertFalse(gate["player_invoked"])
            self.assertFalse(gate["frt_backend_invoked"])
            self.assertFalse(gate["physical_clock_frequency_selected"])
            self.assertFalse(gate["build_time_hardware_io"])
            self.assertFalse(gate["saroo_write"])
            self.assertFalse(gate["behaviorally_active"])

    def test_wrong_r23_manifest_anchor_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r23"
            baseline.mkdir()
            values = _make_r23_baseline(baseline)
            kwargs = _kwargs(values)
            kwargs["expected_baseline_manifest_sha256"] = "0" * 64
            output = root / "r24"
            with self.assertRaisesRegex(SaturnMidi68KR24InertFullBuildGateError, "manifest hash mismatch"):
                prepare_saturn_midi_68k_r24_inert_full_build_gate(
                    baseline, _REFERENCE, output, **kwargs
                )
            self.assertFalse(output.exists())

    def test_run_builds_only_after_safe_preparation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "r23"
            baseline.mkdir()
            values = _make_r23_baseline(baseline)
            output = root / "r24"
            sentinel = object()
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_inert_full_build_gate."
                "build_saturn_standalone_project",
                return_value=sentinel,
            ) as build:
                result = run_saturn_midi_68k_r24_inert_full_build_gate(
                    baseline, _REFERENCE, output, **_kwargs(values)
                )
            self.assertIs(result.build, sentinel)
            build.assert_called_once_with(output.resolve(strict=False))


if __name__ == "__main__":
    unittest.main()
