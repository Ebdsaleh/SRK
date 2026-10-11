"""Regression tests for fresh seven-record resident-decoder candidate preparation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import build_srk_saturn_midi_68k_resident_decoder_image
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_candidate_baseline import SaturnMidi68KResidentDecoderCandidateBaselineError
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_candidate_prepare import (
    SaturnMidi68KResidentDecoderCandidatePrepareError,
    prepare_resident_decoder_physical_candidate,
)


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_SHA = "2" * 64
_HEADER_SHA = "8" * 64
_OBJECT_SHA = "e" * 64


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _write(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _r19_main_fixture() -> bytes:
    slash = chr(92)
    guard = (
        "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
        + slash
        + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)"
    )
    text = (
        "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1\n"
        + guard
        + "\n#include \"srk_saturn_midi_68k_physical_proof.h\"\n#endif\n\n"
        + guard
        + "\n#ifdef SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE\n"
        + "typedef OLD_STATE SRK_MIDI_68K_ACTIVE_PROOF_STATE;\n"
        + "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u\n"
        + "#define SRK_MIDI_68K_PROOF_TITLE \"MIDI / 68K BATCH PROOF\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUBTITLE \"27 records - no MIDI SCSP note\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUCCESS \"Success: sequence=1 index=27 error=0\"\n"
        + "#define SRK_MIDI_68K_PROOF_RESET old_reset\n"
        + "#define SRK_MIDI_68K_PROOF_BEGIN old_begin\n"
        + "#define SRK_MIDI_68K_PROOF_POLL old_poll\n#else\n#endif\n"
        + "static void render(void){\n    char number[11];\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);\n"
        + "    srk_midi_68k_draw_field(2, 11, 14, \"Last error:\");\n"
        + "    srk_midi_68k_draw_field(16, 11, 10, number);\n"
        + "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        + "    srk_midi_68k_draw_field(2, 17, 36, \"Release A to arm proof action\");\n}\n#endif\n"
    )
    return text.encode("utf-8")


def _make_baseline(root: Path):
    baseline = root / "decoder-inert"
    baseline.mkdir()
    runtime = b"accepted inert runtime with resident decoder constant\n"
    files = {
        "src/srk_saturn_main.c": _r19_main_fixture(),
        "src/srk_diag_menu.c": b'entry("MIDI 68K Batch Proof");\n',
        "src/srk_saturn_runtime.c": runtime,
        "src/srk_saturn_midi_68k_resident_decoder.c": b"decoder source\n",
        "src/srk_saturn_midi_68k_resident_decoder.h": b"decoder header\n",
    }
    generated = []
    for relative, data in files.items():
        path = _write(baseline, relative, data)
        generated.append({"path": relative, "size": path.stat().st_size, "sha256": _sha(data)})

    image_sha = build_srk_saturn_midi_68k_resident_decoder_image().sha256
    runtime_sha = _sha(runtime)
    manifest = {
        "schema": "srk.saturn.standalone-project.v1",
        "mode": "standalone-master",
        "policy": {"sd_writes": False, "midi_68k_silent_batch_candidate_bound": True},
        "midi_68k_resident_decoder_full_build_gate": {
            "schema": "srk.saturn.midi-68k-resident-decoder-full-build-gate.v1",
            "existing_r19_candidate_binding_preserved": True,
            "image_sha256": image_sha,
            "source_sha256": _SOURCE_SHA,
            "header_sha256": _HEADER_SHA,
            "accepted_compile_object_sha256_evidence": _OBJECT_SHA,
            "runtime_after_sha256": runtime_sha,
            "decoder_linked": True,
            "decoder_installed": False,
            "decoder_executed": False,
            "decoder_candidate_bound": False,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
            "embedded_records": 0,
            "runtime_record_minimum": 1,
            "runtime_record_maximum": 32,
        },
        "generated_files": generated,
    }
    manifest_path = baseline / "SRK_STANDALONE_PROJECT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_sha = _sha(manifest_path.read_bytes())

    bin_data = b"ACCEPTED-INERT-DECODER-BIN\n"
    cue_data = b"CUE\r\n"
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.bin", bin_data)
    _write(baseline, "build/SRK-Diagnostics/SRK-Diagnostics.cue", cue_data)
    bin_sha, cue_sha = _sha(bin_data), _sha(cue_data)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
        "artifacts": [
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.bin", "size": len(bin_data), "sha256": bin_sha},
            {"path": "build/SRK-Diagnostics/SRK-Diagnostics.cue", "size": len(cue_data), "sha256": cue_sha},
        ],
    }
    (baseline / "SRK_STANDALONE_BUILD.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return baseline, bin_sha, cue_sha, image_sha, runtime_sha


def _prepare(root: Path, output_name: str = "candidate"):
    baseline, bin_sha, cue_sha, image_sha, runtime_sha = _make_baseline(root)
    result = prepare_resident_decoder_physical_candidate(
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


class SaturnMidi68KResidentDecoderCandidatePrepareTests(unittest.TestCase):
    def test_prepares_fresh_candidate_and_preserves_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, bin_sha, cue_sha, image_sha, runtime_sha = _make_baseline(root)
            before = {p.relative_to(baseline).as_posix(): p.read_bytes() for p in baseline.rglob("*") if p.is_file()}
            result = prepare_resident_decoder_physical_candidate(
                baseline, root / "candidate",
                expected_baseline_bin_sha256=bin_sha,
                expected_baseline_cue_sha256=cue_sha,
                expected_image_sha256=image_sha,
                expected_compiler_source_sha256=_SOURCE_SHA,
                expected_compiler_header_sha256=_HEADER_SHA,
                expected_compiler_object_sha256=_OBJECT_SHA,
                expected_runtime_after_sha256=runtime_sha,
            )
            after = {p.relative_to(baseline).as_posix(): p.read_bytes() for p in baseline.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual((result.proof_records, result.proof_final_time_us), (7, 7000))
            main = (result.output_root / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            menu = (result.output_root / "src/srk_diag_menu.c").read_text(encoding="utf-8")
            self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u", main)
            self.assertIn("Processed:", main)
            self.assertIn("Decoder ready:", main)
            self.assertIn("MIDI 68K Decoder Proof", menu)

    def test_manifest_locks_callable_silent_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, result = _prepare(Path(temp_dir))
            manifest = json.loads((result.output_root / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest["midi_68k_resident_decoder_physical_candidate_full_build_gate"]
            self.assertEqual((gate["expected_read_sequence"], gate["expected_read_index"], gate["expected_last_error"]), (1, 7, 0))
            self.assertEqual((gate["proof_records"], gate["proof_final_time_us"]), (7, 7000))
            self.assertTrue(gate["proof_covers_every_srkm_v1_opcode_once"])
            self.assertTrue(gate["decoder_candidate_bound"])
            self.assertFalse(gate["decoder_installed_during_build"])
            self.assertFalse(gate["decoder_executed_during_build"])
            self.assertFalse(gate["midi_scsp_note_attempted"])
            self.assertFalse(gate["saroo_write"])
            self.assertEqual(len(gate["seam_sha256"]), 8)

    def test_runtime_carries_generated_seams_without_scsp_or_smpc_mmio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            _, result = _prepare(Path(temp_dir))
            runtime = (result.output_root / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("RESIDENT DECODER PHYSICAL CANDIDATE", runtime)
            self.assertIn("resident_decoder_install_while_stopped", runtime)
            self.assertIn("proof_preload_publish", runtime)
            self.assertIn("resident_decoder_protocol_poll", runtime)
            self.assertNotIn("0x25B00000", runtime)
            self.assertNotIn("0x2010001F", runtime)

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
            with self.assertRaises(SaturnMidi68KResidentDecoderCandidateBaselineError):
                prepare_resident_decoder_physical_candidate(
                    baseline, root / "bad", expected_runtime_after_sha256="0" * 64, **kwargs
                )
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaisesRegex(SaturnMidi68KResidentDecoderCandidatePrepareError, "already exists"):
                prepare_resident_decoder_physical_candidate(
                    baseline, existing, expected_runtime_after_sha256=runtime_sha, **kwargs
                )

    def test_candidate_prepare_has_no_card_or_deployment_dependency(self):
        source = (_ROOT / "src/rikai_kotoba/hardware/saturn/midi_68k_resident_decoder_candidate_prepare.py").read_text(encoding="utf-8")
        for forbidden in ("card_root", "saroo_deploy", "guarded_deployment", "--apply"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
