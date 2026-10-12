"""Regression tests for the two-phase R24 whole-card guarded deployment."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
    _allowed_paths,
    apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment,
    prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment,
)


_CANDIDATE_MANIFEST = "a" * 64
_CANDIDATE_REPORT = "b" * 64
_BIN = b"R24-REAL-SMF-BIN"
_CUE = b"R24-REAL-SMF-CUE"
_BIN_SHA = sha256(_BIN).hexdigest()
_CUE_SHA = sha256(_CUE).hexdigest()


def _card(root: Path) -> Path:
    card = root / "CARD"
    test = card / "SAROO" / "ISO" / "TEST"
    test.mkdir(parents=True)
    (card / "SAROO" / "ssfirm.bin").write_bytes(b"firmware")
    (card / "SAROO" / "mcuapp.bin").write_bytes(b"mcu")
    (card / "SAROO" / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
    old = test / "OLD-GAME"
    old.mkdir()
    (old / "OLD.BIN").write_bytes(b"old-game")
    (old / "OLD.CUE").write_bytes(b"old-cue")
    return card


def _snapshot(card: Path) -> dict[str, bytes | None]:
    result: dict[str, bytes | None] = {}
    for path in sorted(card.rglob("*"), key=lambda item: str(item).casefold()):
        relative = path.relative_to(card).as_posix()
        result[relative] = path.read_bytes() if path.is_file() else None
    return result


def _pre_media(card: Path):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R24"
    plan = SimpleNamespace(
        destination_directory=destination,
        source_bin=Path("SRK-Diagnostics.bin"),
        source_cue=Path("SRK-Diagnostics.cue"),
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
    )
    return SimpleNamespace(
        plan=plan,
        manifest_sha256=_CANDIDATE_MANIFEST,
        report_sha256=_CANDIDATE_REPORT,
        source_midi_sha256="1" * 64,
        image_sha256="2" * 64,
        candidate_main_sha256="3" * 64,
        candidate_menu_sha256="4" * 64,
        runtime_after_sha256="5" * 64,
        proof_header_sha256="6" * 64,
        proof_source_sha256="7" * 64,
        song_records=310,
        song_batches=10,
        song_duration_us=108151354,
        note_on_count=140,
        note_off_count=140,
        peak_polyphony=2,
        summary_words_verified=256,
        controller_words_verified=1024,
        active_note_words_verified=128,
        deployable_bin_sha256=_BIN_SHA,
        deployable_cue_sha256=_CUE_SHA,
    )


def _deployment(card: Path, *, add_unrelated_change: bool = False, add_extra: bool = False):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R24"
    destination.mkdir()
    bin_path = destination / "SRK-Diagnostics.bin"
    cue_path = destination / "SRK-Diagnostics.cue"
    bin_path.write_bytes(_BIN)
    cue_path.write_bytes(_CUE)
    if add_extra:
        (destination / "SURPRISE.TXT").write_text("unexpected", encoding="utf-8")
    if add_unrelated_change:
        (card / "SAROO" / "saroocfg.txt").write_text("CHANGED\n", encoding="utf-8")
    return SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=bin_path,
        destination_cue=cue_path,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
    )


def _kwargs() -> dict[str, object]:
    return {
        "expected_candidate_manifest_sha256": _CANDIDATE_MANIFEST,
        "expected_candidate_report_sha256": _CANDIDATE_REPORT,
        "expected_baseline_manifest_sha256": "8" * 64,
        "expected_baseline_report_sha256": "9" * 64,
        "expected_baseline_bin_sha256": "c" * 64,
        "expected_baseline_cue_sha256": "d" * 64,
        "expected_image_sha256": "2" * 64,
        "expected_resident_source_sha256": "e" * 64,
        "expected_resident_header_sha256": "f" * 64,
        "expected_voice_header_sha256": "0" * 64,
        "expected_player_source_sha256": "1" * 64,
        "expected_player_header_sha256": "2" * 64,
        "expected_frt_source_sha256": "3" * 64,
        "expected_frt_header_sha256": "4" * 64,
        "expected_stream_source_sha256": "5" * 64,
        "expected_stream_header_sha256": "6" * 64,
        "expected_candidate_main_sha256": "3" * 64,
        "expected_candidate_menu_sha256": "4" * 64,
        "expected_runtime_sha256": "5" * 64,
        "expected_proof_header_sha256": "6" * 64,
        "expected_proof_source_sha256": "7" * 64,
        "expected_bin_sha256": _BIN_SHA,
        "expected_cue_sha256": _CUE_SHA,
        "destination_name": "SRK-Diagnostics-R24",
        "category": "TEST",
    }


def _apply_kwargs() -> tuple[dict[str, object], str, str]:
    values = _kwargs()
    expected_bin = str(values.pop("expected_bin_sha256"))
    expected_cue = str(values.pop("expected_cue_sha256"))
    return values, expected_bin, expected_cue


class SaturnMidi68KR24PhysicalCandidateGuardedDeploymentTests(unittest.TestCase):
    def test_confirmation_token_is_r24_specific(self):
        self.assertEqual(CONFIRMATION_TOKEN, "DEPLOY-R24-REAL-SMF-SONG-PROOF")

    def test_allowed_paths_ignore_root_aliases_and_are_exact(self):
        destination = Path(
            "C:/Users/DEVELO~1.ERI/AppData/Local/Temp/example/CARD/"
            "SAROO/ISO/TEST/SRK-Diagnostics-R24"
        )
        deployment = SimpleNamespace(
            plan=SimpleNamespace(destination_directory=destination),
            destination_bin=destination / "SRK-Diagnostics.bin",
            destination_cue=destination / "SRK-Diagnostics.cue",
        )
        self.assertEqual(
            set(_allowed_paths(deployment)),
            {
                "SAROO/ISO/TEST/SRK-Diagnostics-R24",
                "SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.bin",
                "SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.cue",
            },
        )

    def test_prepare_revalidates_r24_and_creates_off_card_inventory_without_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r24-card-before.json"
            before = _snapshot(card)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ) as inspect:
                result = prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                    root / "candidate", root / "song.mid", card, manifest, **_kwargs()
                )
            self.assertEqual(_snapshot(card), before)
            self.assertTrue(manifest.is_file())
            self.assertTrue(result.exact_verification.valid)
            self.assertEqual(result.pre_media.manifest_sha256, _CANDIDATE_MANIFEST)
            self.assertEqual(result.pre_media.report_sha256, _CANDIDATE_REPORT)
            inspect.assert_called_once()

    def test_prepare_rejects_guard_manifest_on_card_before_pre_media(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
                "outside",
            ):
                prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                    root / "candidate", root / "song.mid", card, card / "guard.json", **_kwargs()
                )

    def test_prepare_rejects_candidate_manifest_drift_before_card_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            values = _kwargs()
            values["expected_candidate_manifest_sha256"] = "0" * 64
            manifest = root / "r24-card-before.json"
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
                    "manifest no longer matches",
                ):
                    prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                        root / "candidate", root / "song.mid", card, manifest, **values
                    )
            self.assertFalse(manifest.exists())

    def test_apply_requires_r24_confirmation_before_any_media_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            before = _snapshot(card)
            values, expected_bin, expected_cue = _apply_kwargs()
            with self.assertRaisesRegex(
                SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
                "DEPLOY-R24-REAL-SMF-SONG-PROOF",
            ):
                apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                    root / "candidate",
                    root / "song.mid",
                    card,
                    root / "missing.json",
                    expected_guard_manifest_sha256="0" * 64,
                    expected_bin_sha256=expected_bin,
                    expected_cue_sha256=expected_cue,
                    confirmation="WRONG",
                    **values,
                )
            self.assertEqual(_snapshot(card), before)

    def test_apply_allows_only_exact_new_r24_directory_and_bin_cue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r24-card-before.json"
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                    root / "candidate", root / "song.mid", card, manifest, **_kwargs()
                )
                values, expected_bin, expected_cue = _apply_kwargs()
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment.apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(card),
                ):
                    result = apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                        root / "candidate",
                        root / "song.mid",
                        card,
                        manifest,
                        expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                        expected_bin_sha256=expected_bin,
                        expected_cue_sha256=expected_cue,
                        confirmation=CONFIRMATION_TOKEN,
                        **values,
                    )
            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual(
                set(result.allowed_changed_paths),
                {
                    "SAROO/ISO/TEST/SRK-Diagnostics-R24",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.bin",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.cue",
                },
            )

    def test_unauthorised_change_does_not_delete_directory_with_surprise_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r24-card-before.json"
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                    root / "candidate", root / "song.mid", card, manifest, **_kwargs()
                )
                values, expected_bin, expected_cue = _apply_kwargs()
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment.apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(
                        card, add_unrelated_change=True, add_extra=True
                    ),
                ):
                    with self.assertRaisesRegex(
                        SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
                        "unauthorized difference.*rollback not attempted",
                    ):
                        apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                            root / "candidate",
                            root / "song.mid",
                            card,
                            manifest,
                            expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                            expected_bin_sha256=expected_bin,
                            expected_cue_sha256=expected_cue,
                            confirmation=CONFIRMATION_TOKEN,
                            **values,
                        )
            destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R24"
            self.assertTrue((destination / "SURPRISE.TXT").is_file())
            self.assertTrue(destination.is_dir())


if __name__ == "__main__":
    unittest.main()
