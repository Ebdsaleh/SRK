"""Regression tests for the two-phase whole-card guarded R21 deployment."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentError,
    _allowed_paths,
    apply_midi_68k_resident_state_physical_candidate_guarded_deployment,
    prepare_midi_68k_resident_state_physical_candidate_guarded_deployment,
)


_IMAGE_SHA = "3" * 64
_SOURCE_SHA = "0" * 64
_HEADER_SHA = "1" * 64
_OBJECT_SHA = "6" * 64
_BIN = b"R21-BIN"
_CUE = b"R21-CUE"
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
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R21"
    plan = SimpleNamespace(
        destination_directory=destination,
        source_bin=Path("SRK-Diagnostics.bin"),
        source_cue=Path("SRK-Diagnostics.cue"),
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
    )
    return SimpleNamespace(
        plan=plan,
        image_sha256=_IMAGE_SHA,
        deployable_bin_sha256=_BIN_SHA,
        deployable_cue_sha256=_CUE_SHA,
        proof_records=20,
        proof_final_time_us=20000,
        summary_words_verified=256,
        controller_words_verified=1024,
        active_note_words_verified=128,
    )


def _deployment(card: Path, *, add_unrelated_change: bool = False, add_extra: bool = False):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R21"
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


def _kwargs() -> dict[str, str]:
    return {
        "expected_image_sha256": _IMAGE_SHA,
        "expected_compiler_source_sha256": _SOURCE_SHA,
        "expected_compiler_header_sha256": _HEADER_SHA,
        "expected_compiler_object_sha256": _OBJECT_SHA,
        "expected_bin_sha256": _BIN_SHA,
        "expected_cue_sha256": _CUE_SHA,
        "destination_name": "SRK-Diagnostics-R21",
        "category": "TEST",
    }


class SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentTests(unittest.TestCase):
    def test_allowed_paths_ignore_windows_long_vs_83_root_aliases(self):
        destination = Path(
            "C:/Users/DEVELO~1.ERI/AppData/Local/Temp/example/CARD/"
            "SAROO/ISO/TEST/SRK-Diagnostics-R21"
        )
        deployment = SimpleNamespace(
            plan=SimpleNamespace(destination_directory=destination),
            destination_bin=destination / "SRK-Diagnostics.bin",
            destination_cue=destination / "SRK-Diagnostics.cue",
        )
        self.assertEqual(
            set(_allowed_paths(deployment)),
            {
                "SAROO/ISO/TEST/SRK-Diagnostics-R21",
                "SAROO/ISO/TEST/SRK-Diagnostics-R21/SRK-Diagnostics.bin",
                "SAROO/ISO/TEST/SRK-Diagnostics-R21/SRK-Diagnostics.cue",
            },
        )

    def test_prepare_revalidates_r21_and_creates_off_card_inventory_without_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r21-card-before.json"
            before = _snapshot(card)
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ) as inspect:
                result = prepare_midi_68k_resident_state_physical_candidate_guarded_deployment(
                    root / "candidate", card, manifest, **_kwargs()
                )
            self.assertEqual(_snapshot(card), before)
            self.assertTrue(manifest.is_file())
            self.assertTrue(result.exact_verification.valid)
            inspect.assert_called_once()

    def test_prepare_refuses_guard_manifest_on_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentError,
                "outside",
            ):
                prepare_midi_68k_resident_state_physical_candidate_guarded_deployment(
                    root / "candidate", card, card / "guard.json", **_kwargs()
                )

    def test_apply_requires_r21_specific_confirmation_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            before = _snapshot(card)
            with self.assertRaisesRegex(
                SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentError,
                "DEPLOY-R21-RESIDENT-STATE-PROOF",
            ):
                apply_midi_68k_resident_state_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    root / "missing.json",
                    expected_guard_manifest_sha256="0" * 64,
                    confirmation="WRONG",
                    **_kwargs(),
                )
            self.assertEqual(_snapshot(card), before)

    def test_apply_allows_only_exact_new_r21_directory_and_bin_cue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r21-card-before.json"
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_midi_68k_resident_state_physical_candidate_guarded_deployment(
                    root / "candidate", card, manifest, **_kwargs()
                )
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment.apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(card),
                ):
                    result = apply_midi_68k_resident_state_physical_candidate_guarded_deployment(
                        root / "candidate",
                        card,
                        manifest,
                        expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                        confirmation=CONFIRMATION_TOKEN,
                        **_kwargs(),
                    )
            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual(
                set(result.allowed_changed_paths),
                {
                    "SAROO/ISO/TEST/SRK-Diagnostics-R21",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R21/SRK-Diagnostics.bin",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R21/SRK-Diagnostics.cue",
                },
            )

    def test_unauthorised_change_blocks_rollback_deletion_when_extra_file_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r21-card-before.json"
            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment._inspect_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_midi_68k_resident_state_physical_candidate_guarded_deployment(
                    root / "candidate", card, manifest, **_kwargs()
                )
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_guarded_deployment.apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(
                        card, add_unrelated_change=True, add_extra=True
                    ),
                ):
                    with self.assertRaisesRegex(
                        SaturnMidi68KResidentStatePhysicalCandidateGuardedDeploymentError,
                        "unauthorised difference.*rollback not attempted",
                    ):
                        apply_midi_68k_resident_state_physical_candidate_guarded_deployment(
                            root / "candidate",
                            card,
                            manifest,
                            expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                            confirmation=CONFIRMATION_TOKEN,
                            **_kwargs(),
                        )
            destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R21"
            self.assertTrue((destination / "SURPRISE.TXT").is_file())
            self.assertTrue(destination.is_dir())


if __name__ == "__main__":
    unittest.main()
