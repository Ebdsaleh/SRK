"""Regression contracts for the R25 RR calibration fresh full-build gate."""

from __future__ import annotations

from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_full_build_gate as _gate
from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_full_build_gate import (
    prepare_saturn_midi_68k_r24_physical_candidate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_full_build_gate import (
    SaturnMidi68KR25RRCalibrationFullBuildGateError,
    prepare_saturn_midi_68k_r25_rr_calibration_candidate,
    run_saturn_midi_68k_r25_rr_calibration_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
)
from tests.test_saturn_midi_68k_r24_physical_candidate_full_build_gate import (
    _kwargs,
    _make_inert_baseline,
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


def _make_r24_physical_baseline(root: Path) -> tuple[Path, dict[str, object]]:
    inert = root / "inert"
    inert.mkdir()
    inert_values = _make_inert_baseline(inert)
    physical = root / "r24-physical"
    prepared = prepare_saturn_midi_68k_r24_physical_candidate(
        inert,
        _REFERENCE,
        physical,
        **_kwargs(inert_values),
    )

    deploy_bin = b"synthetic accepted r24 physical bin"
    deploy_cue = b'FILE "SRK-Diagnostics.bin" BINARY\n'
    _write(physical, "build/SRK-Diagnostics/SRK-Diagnostics.bin", deploy_bin)
    _write(physical, "build/SRK-Diagnostics/SRK-Diagnostics.cue", deploy_cue)
    manifest_path = physical / "SRK_STANDALONE_PROJECT.json"
    manifest_sha = _sha_file(manifest_path)
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": manifest_sha,
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
    report_path = physical / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    representation = {
        relative: _sha_file(physical / relative)
        for relative in _gate._ACCEPTED_R24_REPRESENTATION
    }
    values: dict[str, object] = {
        "manifest": manifest_sha,
        "report": _sha_file(report_path),
        "bin": _sha(deploy_bin),
        "cue": _sha(deploy_cue),
        "image": prepared.image_sha256,
        "main": prepared.candidate_main_sha256,
        "menu": prepared.candidate_menu_sha256,
        "runtime": prepared.runtime_after_sha256,
        "proof_header": prepared.proof_header_sha256,
        "proof_source": prepared.proof_source_sha256,
        "representation": representation,
    }
    return physical, values


def _patched_anchors(values: dict[str, object]) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(
        patch.multiple(
            _gate,
            ACCEPTED_R24_MANIFEST_SHA256=values["manifest"],
            ACCEPTED_R24_REPORT_SHA256=values["report"],
            ACCEPTED_R24_BIN_SHA256=values["bin"],
            ACCEPTED_R24_CUE_SHA256=values["cue"],
            ACCEPTED_R24_IMAGE_SHA256=values["image"],
            ACCEPTED_R24_MAIN_SHA256=values["main"],
            ACCEPTED_R24_MENU_SHA256=values["menu"],
            ACCEPTED_R24_RUNTIME_SHA256=values["runtime"],
            ACCEPTED_R24_PROOF_HEADER_SHA256=values["proof_header"],
            ACCEPTED_R24_PROOF_SOURCE_SHA256=values["proof_source"],
        )
    )
    stack.enter_context(
        patch.object(_gate, "_ACCEPTED_R24_REPRESENTATION", values["representation"])
    )
    return stack


class SaturnMidi68KR25RRCalibrationFullBuildGateTests(unittest.TestCase):
    def test_prepare_preserves_r24_and_creates_fresh_rr16_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, values = _make_r24_physical_baseline(root)
            before = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            output = root / "r25-rr16"
            with _patched_anchors(values):
                prepared = prepare_saturn_midi_68k_r25_rr_calibration_candidate(
                    baseline,
                    output,
                    release_rate=16,
                )
            after = {
                path.relative_to(baseline): path.read_bytes()
                for path in baseline.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(prepared.release_rate, 16)
            self.assertEqual(prepared.eg2_word, 0x3C10)
            self.assertEqual(prepared.runtime_before_sha256, values["runtime"])
            main = (output / "src/srk_saturn_main.c").read_text(encoding="utf-8")
            runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
            self.assertIn("SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE", main)
            self.assertIn("production RR UNSET", main)
            self.assertIn("R25 RR PHYSICAL CALIBRATION", runtime)
            self.assertTrue(
                (output / "src/srk_saturn_midi_68k_r25_rr_calibration_proof.c").is_file()
            )

    def test_manifest_records_operator_observation_and_no_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, values = _make_r24_physical_baseline(root)
            output = root / "r25-rr16"
            with _patched_anchors(values):
                prepare_saturn_midi_68k_r25_rr_calibration_candidate(
                    baseline,
                    output,
                    release_rate=16,
                )
            manifest = json.loads((output / "SRK_STANDALONE_PROJECT.json").read_text(encoding="utf-8"))
            gate = manifest[_gate._GATE_KEY]
            self.assertEqual(gate["release_rate"], 16)
            self.assertEqual(gate["note"], 69)
            self.assertEqual(gate["note_off_us"], 1250000)
            self.assertEqual(gate["observation_window_us"], 2000000)
            self.assertEqual(gate["observation_end_us"], 3250000)
            self.assertEqual(gate["measurement_mode"], "operator-observed-audio")
            self.assertFalse(gate["envelope_readback_available"])
            self.assertFalse(gate["production_rr_selected"])
            self.assertFalse(gate["build_time_hardware_io"])
            self.assertFalse(gate["saroo_write"])
            self.assertTrue(gate["off_card_only"])

    def test_run_calls_normal_builder_only_after_safe_fresh_preparation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline, values = _make_r24_physical_baseline(root)
            output = root / "r25-rr16"
            fake_build = SimpleNamespace(successful=True)
            with _patched_anchors(values), patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_full_build_gate."
                "build_saturn_standalone_project",
                return_value=fake_build,
            ) as builder:
                result = run_saturn_midi_68k_r25_rr_calibration_full_build_gate(
                    baseline,
                    output,
                    release_rate=16,
                )
            self.assertIs(result.build, fake_build)
            builder.assert_called_once_with(output.resolve(strict=False))


if __name__ == "__main__":
    unittest.main()
