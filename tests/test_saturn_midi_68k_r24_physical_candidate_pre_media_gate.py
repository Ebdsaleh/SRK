"""Regression contracts for the independent R24 real-song pre-media gate."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_full_build_gate import (
    prepare_saturn_midi_68k_r24_physical_candidate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_pre_media_gate import (
    SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
    inspect_saturn_midi_68k_r24_physical_candidate_pre_media,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from tests.test_saturn_midi_68k_r24_physical_candidate_full_build_gate import (
    _kwargs as _build_kwargs,
    _make_inert_baseline,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha(path.read_bytes())


def _fixture(root: Path) -> tuple[Path, Path, dict[str, str]]:
    baseline = root / "inert"
    baseline.mkdir()
    values = _make_inert_baseline(baseline)
    candidate = root / "candidate"
    prepare_saturn_midi_68k_r24_physical_candidate(
        baseline,
        _REFERENCE,
        candidate,
        **_build_kwargs(values),
    )

    deploy = candidate / "build" / "SRK-Diagnostics"
    deploy.mkdir(parents=True, exist_ok=True)
    bin_payload = b"r24-physical-candidate-bin"
    cue_payload = b"r24-physical-candidate-cue"
    bin_path = deploy / "SRK-Diagnostics.bin"
    cue_path = deploy / "SRK-Diagnostics.cue"
    bin_path.write_bytes(bin_payload)
    cue_path.write_bytes(cue_payload)

    manifest_path = candidate / "SRK_STANDALONE_PROJECT.json"
    report = {
        "schema": "srk.saturn.standalone-build.v1",
        "successful": True,
        "project_manifest_sha256": _sha_file(manifest_path),
        "artifacts": [
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.bin",
                "size": len(bin_payload),
                "sha256": _sha(bin_payload),
            },
            {
                "path": "build/SRK-Diagnostics/SRK-Diagnostics.cue",
                "size": len(cue_payload),
                "sha256": _sha(cue_payload),
            },
        ],
    }
    report_path = candidate / "SRK_STANDALONE_BUILD.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    accepted = {
        **values,
        "candidate_main": _sha_file(candidate / "src/srk_saturn_main.c"),
        "candidate_menu": _sha_file(candidate / "src/srk_diag_menu.c"),
        "runtime": _sha_file(candidate / "src/srk_saturn_runtime.c"),
        "proof_header": _sha_file(candidate / "src/srk_saturn_midi_68k_r24_physical_proof.h"),
        "proof_source": _sha_file(candidate / "src/srk_saturn_midi_68k_r24_physical_proof.c"),
        "stream_source": _sha(
            render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
        ),
        "stream_header": _sha(
            render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
        ),
        "candidate_bin": _sha(bin_payload),
        "candidate_cue": _sha(cue_payload),
    }
    return baseline, candidate, accepted


def _inspect_kwargs(values: dict[str, str]) -> dict[str, str]:
    return {
        "expected_baseline_manifest_sha256": values["manifest"],
        "expected_baseline_report_sha256": values["report"],
        "expected_baseline_bin_sha256": values["bin"],
        "expected_baseline_cue_sha256": values["cue"],
        "expected_image_sha256": values["image"],
        "expected_resident_source_sha256": values["resident_source"],
        "expected_resident_header_sha256": values["resident_header"],
        "expected_voice_header_sha256": values["voice_header"],
        "expected_player_source_sha256": values["player_source"],
        "expected_player_header_sha256": values["player_header"],
        "expected_frt_source_sha256": values["frt_source"],
        "expected_frt_header_sha256": values["frt_header"],
        "expected_stream_source_sha256": values["stream_source"],
        "expected_stream_header_sha256": values["stream_header"],
        "expected_candidate_main_sha256": values["candidate_main"],
        "expected_candidate_menu_sha256": values["candidate_menu"],
        "expected_runtime_sha256": values["runtime"],
        "expected_proof_header_sha256": values["proof_header"],
        "expected_proof_source_sha256": values["proof_source"],
        "expected_bin_sha256": values["candidate_bin"],
        "expected_cue_sha256": values["candidate_cue"],
        "destination_name": "SRK-Diagnostics-R24",
        "category": "TEST",
    }


def _plan(card: Path, candidate: Path, values: dict[str, str]):
    category = card / "SAROO" / "ISO" / "TEST"
    return SimpleNamespace(
        card_root=card,
        project_root=candidate,
        category_directory=category,
        destination_directory=category / "SRK-Diagnostics-R24",
        source_bin=candidate / "build/SRK-Diagnostics/SRK-Diagnostics.bin",
        source_cue=candidate / "build/SRK-Diagnostics/SRK-Diagnostics.cue",
        bin_size=(candidate / "build/SRK-Diagnostics/SRK-Diagnostics.bin").stat().st_size,
        cue_size=(candidate / "build/SRK-Diagnostics/SRK-Diagnostics.cue").stat().st_size,
        bin_sha256=values["candidate_bin"],
        cue_sha256=values["candidate_cue"],
        sector_count=128,
        raw_bytes=301056,
    )


class SaturnMidi68KR24PhysicalCandidatePreMediaGateTests(unittest.TestCase):
    def test_independent_gate_reproves_complete_song_and_external_hashes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            card = root / "CARD"
            card.mkdir()
            fake_plan = _plan(card, candidate, values)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=fake_plan,
            ):
                result = inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    card,
                    **_inspect_kwargs(values),
                )
            self.assertEqual(result.song_records, 310)
            self.assertEqual(result.song_batches, 10)
            self.assertEqual(result.song_duration_us, 108151354)
            self.assertEqual((result.note_on_count, result.note_off_count), (140, 140))
            self.assertEqual(result.peak_polyphony, 2)
            self.assertEqual(
                (
                    result.summary_words_verified,
                    result.controller_words_verified,
                    result.active_note_words_verified,
                ),
                (256, 1024, 128),
            )
            self.assertEqual(result.deployable_bin_sha256, values["candidate_bin"])
            self.assertEqual(result.deployable_cue_sha256, values["candidate_cue"])

    def test_wrong_externally_accepted_candidate_main_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            kwargs = _inspect_kwargs(values)
            kwargs["expected_candidate_main_sha256"] = "f" * 64
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
                "externally accepted hash mismatch",
            ):
                inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    root / "CARD",
                    **kwargs,
                )

    def test_wrong_accepted_inert_chain_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            kwargs = _inspect_kwargs(values)
            kwargs["expected_baseline_manifest_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
                "accepted inert chain mismatch",
            ):
                inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    root / "CARD",
                    **kwargs,
                )

    def test_generated_proof_tamper_is_rejected_before_media_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            proof = candidate / "src/srk_saturn_midi_68k_r24_physical_proof.c"
            proof.write_text(proof.read_text(encoding="utf-8") + "/* tamper */\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
                "generated input changed",
            ):
                inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    root / "CARD",
                    **_inspect_kwargs(values),
                )

    def test_build_report_candidate_bin_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            report_path = candidate / "SRK_STANDALONE_BUILD.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["artifacts"][0]["sha256"] = "0" * 64
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
                "candidate BIN report hash mismatch",
            ):
                inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    root / "CARD",
                    **_inspect_kwargs(values),
                )

    def test_media_planner_is_called_read_only_for_fresh_r24_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, candidate, values = _fixture(root)
            card = root / "CARD"
            card.mkdir()
            before = list(card.rglob("*"))
            fake_plan = _plan(card, candidate, values)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_pre_media_gate."
                "plan_saroo_standalone_image_deployment",
                return_value=fake_plan,
            ) as planner:
                inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
                    candidate,
                    _REFERENCE,
                    card,
                    **_inspect_kwargs(values),
                )
            planner.assert_called_once_with(
                card,
                candidate.resolve(strict=False),
                destination_name="SRK-Diagnostics-R24",
                category="TEST",
            )
            self.assertEqual(before, list(card.rglob("*")))


if __name__ == "__main__":
    unittest.main()
