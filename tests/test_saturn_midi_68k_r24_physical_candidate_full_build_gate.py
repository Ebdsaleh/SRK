"""Regression contracts for the R24 real-SMF physical full-build gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate as _r23
from rikai_kotoba.hardware.saturn.midi_68k_r24_frt_backend import (
    render_saturn_midi_68k_r24_frt_backend_header,
    render_saturn_midi_68k_r24_frt_backend_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_full_build_gate import (
    SaturnMidi68KR24PhysicalCandidateFullBuildGateError,
    prepare_saturn_midi_68k_r24_physical_candidate,
    run_saturn_midi_68k_r24_physical_candidate_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_player import (
    render_saturn_midi_68k_r24_player_header,
    render_saturn_midi_68k_r24_player_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
    render_srk_saturn_midi_68k_r24_resident_audio_service_header,
    render_srk_saturn_midi_68k_r24_resident_audio_service_source,
    render_srk_saturn_midi_68k_r24_voice_header,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    build_saturn_midi_68k_r24_song_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from tests.test_saturn_midi_68k_resident_audio_candidate_prepare import (
    _synthetic_stream_main,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(path.read_bytes())


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _make_inert_baseline(root: Path) -> dict[str, str]:
    profile = build_saturn_midi_68k_r24_song_profile(_REFERENCE)
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    r23_main = _r23.derive_resident_audio_candidate_main(_synthetic_stream_main()).encode("utf-8")
    r23_menu = _r23.derive_resident_audio_candidate_menu(
        'x\n"MIDI 68K Stream Proof"\ny\n'
    ).encode("utf-8")
    runtime = b"/* accepted R24 inert runtime */\n"
    resident_source = render_srk_saturn_midi_68k_r24_resident_audio_service_source().encode("utf-8")
    resident_header = render_srk_saturn_midi_68k_r24_resident_audio_service_header().encode("utf-8")
    voice_header = render_srk_saturn_midi_68k_r24_voice_header().encode("utf-8")
    player_source = render_saturn_midi_68k_r24_player_source(profile.program).encode("utf-8")
    player_header = render_saturn_midi_68k_r24_player_header().encode("utf-8")
    frt_source = render_saturn_midi_68k_r24_frt_backend_source().encode("utf-8")
    frt_header = render_saturn_midi_68k_r24_frt_backend_header().encode("utf-8")
    stream_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    stream_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")

    files = {
        "src/srk_saturn_main.c": r23_main,
        "src/srk_diag_menu.c": r23_menu,
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_r24_resident_audio_service.c": resident_source,
        "src/srk_saturn_midi_68k_r24_resident_audio_service.h": resident_header,
        "src/srk_saturn_midi_68k_r24_voice_state.h": voice_header,
        "src/srk_saturn_midi_68k_r24_player.c": player_source,
        "src/srk_saturn_midi_68k_r24_player.h": player_header,
        "src/srk_saturn_midi_68k_r24_frt_backend.c": frt_source,
        "src/srk_saturn_midi_68k_r24_frt_backend.h": frt_header,
        "src/srk_saturn_midi_68k_stream_service.c": stream_source,
        "src/srk_saturn_midi_68k_stream_service.h": stream_header,
    }
    for relative, payload in files.items():
        _write(root, relative, payload)

    deploy_bin = b"accepted-r24-inert-bin"
    deploy_cue = b'FILE "SRK-Diagnostics.bin" BINARY\n'
    _write(root, "build/SRK-Diagnostics/SRK-Diagnostics.bin", deploy_bin)
    _write(root, "build/SRK-Diagnostics/SRK-Diagnostics.cue", deploy_cue)

    gate = {
        "schema": "srk.saturn.midi-68k-r24-inert-full-build-gate.v1",
        "accepted_r23_candidate_binding_preserved": True,
        "r23_main_sha256": _sha(r23_main),
        "r23_menu_sha256": _sha(r23_menu),
        "source_midi_sha256": profile.source_sha256,
        "song_records": profile.record_count,
        "song_duration_us": profile.duration_us,
        "song_batches": len(profile.batches),
        "song_batch_sizes": [batch.record_count for batch in profile.batches],
        "peak_polyphony": profile.peak_polyphony,
        "r24_image_sha256": image.sha256,
        "r24_resident_source_sha256": _sha(resident_source),
        "r24_resident_header_sha256": _sha(resident_header),
        "r24_voice_header_sha256": _sha(voice_header),
        "r24_player_source_sha256": _sha(player_source),
        "r24_player_header_sha256": _sha(player_header),
        "r24_frt_source_sha256": _sha(frt_source),
        "r24_frt_header_sha256": _sha(frt_header),
        "runtime_after_sha256": _sha(runtime),
        "resident_linked_as_constant_data": True,
        "resident_installed": False,
        "resident_executed": False,
        "player_linked": True,
        "player_invoked": False,
        "frt_backend_linked": True,
        "frt_backend_invoked": False,
        "physical_clock_frequency_selected": False,
        "scsp_mmio_executed": False,
        "sound_ram_writes": False,
        "frt_mmio_executed": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active": False,
    }
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_r24_inert_full_build_gate": gate,
        "generated_files": [
            {"path": relative, "size": len(payload), "sha256": _sha(payload)}
            for relative, payload in sorted(files.items())
        ],
    }
    manifest_path = root / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": _sha_file(manifest_path),
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "sha256": _sha(deploy_bin),
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "sha256": _sha(deploy_cue),
            },
        ],
    }
    report_path = root / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": _sha_file(manifest_path),
        "report": _sha_file(report_path),
        "bin": _sha(deploy_bin),
        "cue": _sha(deploy_cue),
        "runtime": _sha(runtime),
        "image": image.sha256,
        "resident_source": _sha(resident_source),
        "resident_header": _sha(resident_header),
        "voice_header": _sha(voice_header),
        "player_source": _sha(player_source),
        "player_header": _sha(player_header),
        "frt_source": _sha(frt_source),
        "frt_header": _sha(frt_header),
    }


def _kwargs(values: dict[str, str]) -> dict[str, str]:
    return {
        "expected_baseline_bin_sha256": values["bin"],
        "expected_baseline_cue_sha256": values["cue"],
        "expected_baseline_runtime_sha256": values["runtime"],
        "expected_image_sha256": values["image"],
        "expected_resident_source_sha256": values["resident_source"],
        "expected_resident_header_sha256": values["resident_header"],
        "expected_voice_header_sha256": values["voice_header"],
        "expected_player_source_sha256": values["player_source"],
        "expected_player_header_sha256": values["player_header"],
        "expected_frt_source_sha256": values["frt_source"],
        "expected_frt_header_sha256": values["frt_header"],
    }


class SaturnMidi68KR24PhysicalCandidateFullBuildGateTests(unittest.TestCase):
    def test_prepare_derives_fresh_candidate_without_mutating_inert_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            values = _make_inert_baseline(baseline)
            before = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            output = root / "candidate"
            prepared = prepare_saturn_midi_68k_r24_physical_candidate(
                baseline,
                _REFERENCE,
                output,
                **_kwargs(values),
            )
            after = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(prepared.baseline_manifest_sha256, values["manifest"])
            self.assertEqual(prepared.baseline_report_sha256, values["report"])
            self.assertEqual(prepared.song_records, 310)
            self.assertEqual(prepared.song_batches, 10)
            self.assertEqual(prepared.song_duration_us, 108151354)
            main = (output / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (output / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE", main)
            self.assertIn("MIDI / 68K REAL SONG", main)
            self.assertIn('"MIDI 68K Song Proof"', menu)
            self.assertIn("R24 REAL-SMF PHYSICAL CANDIDATE", runtime)
            self.assertTrue((output / "src/srk_saturn_midi_68k_r24_physical_proof.c").is_file())

    def test_manifest_locks_physical_song_clock_and_voice_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            values = _make_inert_baseline(baseline)
            output = root / "candidate"
            prepare_saturn_midi_68k_r24_physical_candidate(
                baseline,
                _REFERENCE,
                output,
                **_kwargs(values),
            )
            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_r24_physical_candidate_full_build_gate"]
            self.assertEqual(gate["proof_records"], 310)
            self.assertEqual(gate["queue_batches"], 10)
            self.assertEqual(gate["batch_sizes"], [32] * 9 + [22])
            self.assertEqual(gate["expected_note_on_count"], 140)
            self.assertEqual(gate["expected_note_off_count"], 140)
            self.assertEqual(gate["expected_peak_polyphony"], 2)
            self.assertEqual(gate["expected_busy_count"], 0)
            self.assertEqual(gate["expected_final_active_count"], 0)
            self.assertEqual(gate["state_summary_words_verified"], 256)
            self.assertEqual(gate["controller_words_verified"], 1024)
            self.assertEqual(gate["active_note_words_verified"], 128)
            self.assertEqual(gate["clock_ntsc_a_hz"], 26874100)
            self.assertEqual(gate["clock_ntsc_b_hz"], 28636400)
            self.assertEqual(gate["clock_pal_a_hz"], 26687700)
            self.assertEqual(gate["clock_pal_b_hz"], 28437700)
            self.assertTrue(gate["frt_original_tcr_restored_on_terminal_path"])
            self.assertFalse(gate["build_time_hardware_io"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])

    def test_wrong_inert_bin_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            values = _make_inert_baseline(baseline)
            kwargs = _kwargs(values)
            kwargs["expected_baseline_bin_sha256"] = "f" * 64
            output = root / "candidate"
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidateFullBuildGateError,
                "R24 inert BIN",
            ):
                prepare_saturn_midi_68k_r24_physical_candidate(
                    baseline,
                    _REFERENCE,
                    output,
                    **kwargs,
                )
            self.assertFalse(output.exists())

    def test_run_invokes_normal_builder_only_after_safe_preparation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = root / "inert"
            baseline.mkdir()
            values = _make_inert_baseline(baseline)
            output = root / "candidate"
            fake_build = SimpleNamespace(successful=True)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_full_build_gate."
                "build_saturn_standalone_project",
                return_value=fake_build,
            ) as builder:
                result = run_saturn_midi_68k_r24_physical_candidate_full_build_gate(
                    baseline,
                    _REFERENCE,
                    output,
                    **_kwargs(values),
                )
            self.assertIs(result.build, fake_build)
            builder.assert_called_once_with(output.resolve(strict=False))


if __name__ == "__main__":
    unittest.main()
