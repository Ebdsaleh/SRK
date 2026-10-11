"""Regression tests for the fresh Phase-B full-state candidate preparation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder import (
    build_srk_saturn_midi_68k_resident_state_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_candidate_baseline import (
    SaturnMidi68KResidentStateCandidateBaselineError,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_candidate_prepare import (
    SaturnMidi68KResidentStateCandidatePrepareError,
    prepare_resident_state_decoder_physical_candidate,
)


_SOURCE_SHA = "0edb77a5be40b6324166d72d53ae7ebcf9ce79ba3799b2d3cc8055aa11ead016"
_HEADER_SHA = "01ce4a0e477830887feb7a92d41e1e1caefedacc6fed87bfa0805d9aeb7ff589"
_OBJECT_SHA = "6ce6a594361fbad251ae491538a181c108b1a76ddd185e3e3924e5b354d199d7"


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _r20_main_fixture() -> bytes:
    slash = chr(92)
    guard = (
        "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
        + slash
        + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE) || "
        + slash
        + "\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)"
    )
    text = (
        "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1\n"
        + guard
        + "\n#include \"srk_saturn_midi_68k_physical_proof.h\"\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "#include \"srk_saturn_midi_68k_resident_decoder_physical_proof.h\"\n"
        + "#endif\n#endif\n\n"
        + guard
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "typedef OLD_STATE SRK_MIDI_68K_ACTIVE_PROOF_STATE;\n"
        + "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u\n"
        + "#define SRK_MIDI_68K_PROOF_TITLE \"MIDI / 68K DECODER PROOF\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUBTITLE \"7 runtime records - no MIDI SCSP note\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUCCESS \"Success: sequence=1 index=7 error=0\"\n"
        + "#define SRK_MIDI_68K_PROOF_RESET old_reset\n"
        + "#define SRK_MIDI_68K_PROOF_BEGIN old_begin\n"
        + "#define SRK_MIDI_68K_PROOF_POLL old_poll\n"
        + "#elif defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)\n"
        + "#endif\n"
        + "static void render(void){\n    char number[11];\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);\n"
        + "    srk_midi_68k_draw_field(2, 11, 14, \"Last error:\");\n"
        + "    srk_midi_68k_draw_field(16, 11, 10, number);\n\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.processed);\n"
        + "    srk_midi_68k_draw_field(2, 12, 14, \"Processed:\");\n"
        + "    srk_midi_68k_draw_field(16, 12, 10, number);\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.current_record);\n"
        + "    srk_midi_68k_draw_field(2, 13, 14, \"Current:\");\n"
        + "    srk_midi_68k_draw_field(16, 13, 10, number);\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.decoder_ready);\n"
        + "    srk_midi_68k_draw_field(2, 14, 14, \"Decoder ready:\");\n"
        + "    srk_midi_68k_draw_field(16, 14, 10, number);\n"
        + "#endif\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "    srk_midi_68k_draw_field(2, 15, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        + "#else\n"
        + "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        + "#endif\n"
        + "    srk_midi_68k_draw_field(2, 17, 36, \"Release A to arm proof action\");\n"
        + "}\n#endif\n"
    )
    return text.encode("utf-8")


def _make_baseline(root: Path):
    baseline = root / "phase-b-inert"
    baseline.mkdir()
    runtime = b"accepted Phase-B inert runtime with compiler-accepted state decoder\n"
    files = {
        "src/srk_saturn_main.c": _r20_main_fixture(),
        "src/srk_diag_menu.c": b'entry("MIDI 68K Decoder Proof");\n',
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_resident_state_decoder.c": b"state decoder source\n",
        "src/srk_saturn_midi_68k_resident_state_decoder.h": b"state decoder header\n",
    }
    generated = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        generated.append(
            {"path": relative, "size": path.stat().st_size, "sha256": _sha(data)}
        )

    image_sha = build_srk_saturn_midi_68k_resident_state_decoder_image().sha256
    runtime_sha = _sha(runtime)
    main_sha = _sha(files["src/srk_saturn_main.c"])
    menu_sha = _sha(files["src/srk_diag_menu.c"])
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False},
        "midi_68k_resident_state_decoder_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-state-decoder-full-build-gate.v1",
            "existing_r20_candidate_binding_preserved": True,
            "r20_main_sha256": main_sha,
            "r20_menu_sha256": menu_sha,
            "image_sha256": image_sha,
            "source_sha256": _SOURCE_SHA,
            "header_sha256": _HEADER_SHA,
            "accepted_compile_object_sha256_evidence": _OBJECT_SHA,
            "runtime_after_sha256": runtime_sha,
            "runtime_record_minimum": 1,
            "runtime_record_maximum": 32,
            "dynamic_state_mutation": True,
            "state_decoder_linked": True,
            "state_decoder_installed": False,
            "state_decoder_executed": False,
            "state_decoder_candidate_bound": False,
            "midi_scsp_note_attempted": False,
            "build_time_hardware_io": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
        },
        "generated_files": generated,
    }
    manifest_path = baseline / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_sha = _sha(manifest_path.read_bytes())

    bin_data = b"PHASE-B-INERT-BIN\n"
    cue_data = b"CUE\r\n"
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.bin", bin_data)
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.cue", cue_data)
    bin_sha, cue_sha = _sha(bin_data), _sha(cue_data)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "size": len(bin_data),
                "sha256": bin_sha,
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "size": len(cue_data),
                "sha256": cue_sha,
            },
        ],
    }
    (baseline / "SRK_STANDALONE_BUILD.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return baseline, bin_sha, cue_sha, image_sha, runtime_sha


def _prepare(root: Path, output_name: str = "candidate"):
    baseline, bin_sha, cue_sha, image_sha, runtime_sha = _make_baseline(root)
    result = prepare_resident_state_decoder_physical_candidate(
        baseline,
        root / output_name,
        expected_baseline_bin_sha256=bin_sha,
        expected_baseline_cue_sha256=cue_sha,
        expected_image_sha256=image_sha,
        expected_compiler_source_sha256=_SOURCE_SHA,
        expected_compiler_header_sha256=_HEADER_SHA,
        expected_compiler_object_sha256=_OBJECT_SHA,
        expected_runtime_after_sha256=runtime_sha,
    )
    return baseline, result


class SaturnMidi68KResidentStateCandidatePrepareTests(unittest.TestCase):
    def test_prepares_fresh_candidate_and_preserves_inert_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, bin_sha, cue_sha, image_sha, runtime_sha = _make_baseline(root)
            before = {
                p.relative_to(baseline).as_posix(): p.read_bytes()
                for p in baseline.rglob("*")
                if p.is_file()
            }
            result = prepare_resident_state_decoder_physical_candidate(
                baseline,
                root / "candidate",
                expected_baseline_bin_sha256=bin_sha,
                expected_baseline_cue_sha256=cue_sha,
                expected_image_sha256=image_sha,
                expected_compiler_source_sha256=_SOURCE_SHA,
                expected_compiler_header_sha256=_HEADER_SHA,
                expected_compiler_object_sha256=_OBJECT_SHA,
                expected_runtime_after_sha256=runtime_sha,
            )
            after = {
                p.relative_to(baseline).as_posix(): p.read_bytes()
                for p in baseline.rglob("*")
                if p.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual((result.proof_records, result.proof_final_time_us), (20, 20000))
            self.assertEqual(
                (
                    result.state_summary_words_verified,
                    result.controller_words_verified,
                    result.active_note_words_verified,
                ),
                (256, 1024, 128),
            )

    def test_candidate_main_menu_and_manifest_expose_full_state_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, result = _prepare(Path(temp_dir))
            main = (result.output_root / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (result.output_root / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            manifest = json.loads(
                (result.output_root / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8")
            )
            gate = manifest[
                "midi_68k_resident_state_decoder_physical_candidate_full_build_gate"
            ]
            self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u", main)
            self.assertIn("State verify:", main)
            self.assertIn("CH3 program:", main)
            self.assertIn("MIDI 68K State Proof", menu)
            self.assertEqual(gate["expected_read_index"], 20)
            self.assertTrue(gate["state_verification_required"])
            self.assertEqual(
                (
                    gate["state_summary_words_verified"],
                    gate["controller_words_verified"],
                    gate["active_note_words_verified"],
                ),
                (256, 1024, 128),
            )
            self.assertEqual(gate["expected_state_snapshot"]["ch3_pitch_bend"], 10036)
            self.assertEqual(gate["expected_state_snapshot"]["ch3_cc74"], 66)
            self.assertEqual(len(gate["seam_sha256"]), 10)

    def test_runtime_carries_state_verifier_and_no_audio_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, result = _prepare(Path(temp_dir))
            runtime = (result.output_root / "src/srk_saturn_runtime.c").read_text(
                encoding="utf-8"
            )
            self.assertIn("RESIDENT STATE DECODER PHYSICAL CANDIDATE", runtime)
            self.assertIn("expected_summary_words", runtime)
            self.assertIn("expected_controller_words", runtime)
            self.assertIn("expected_active_words", runtime)
            self.assertIn("resident_state_protocol_poll", runtime)
            self.assertNotIn("0x25B00000", runtime)

    def test_rejects_wrong_runtime_evidence_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, bin_sha, cue_sha, image_sha, runtime_sha = _make_baseline(root)
            kwargs = dict(
                expected_baseline_bin_sha256=bin_sha,
                expected_baseline_cue_sha256=cue_sha,
                expected_image_sha256=image_sha,
                expected_compiler_source_sha256=_SOURCE_SHA,
                expected_compiler_header_sha256=_HEADER_SHA,
                expected_compiler_object_sha256=_OBJECT_SHA,
            )
            with self.assertRaises(SaturnMidi68KResidentStateCandidateBaselineError):
                prepare_resident_state_decoder_physical_candidate(
                    baseline,
                    root / "bad",
                    expected_runtime_after_sha256="0" * 64,
                    **kwargs,
                )
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStateCandidatePrepareError, "already exists"
            ):
                prepare_resident_state_decoder_physical_candidate(
                    baseline,
                    existing,
                    expected_runtime_after_sha256=runtime_sha,
                    **kwargs,
                )

    def test_candidate_prepare_remains_off_card_only(self):
        import rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_candidate_prepare as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("card_root", "guarded_deployment", "--apply"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
