"""Regression tests for the two-phase whole-card guarded R19 deployment."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError,
    _allowed_paths,
    apply_midi_68k_silent_batch_physical_candidate_guarded_deployment,
    prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment,
)


_IMAGE_SHA = "d" * 64
_BIN = b"R19-BIN"
_CUE = b"R19-CUE"
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
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R19"
    plan = SimpleNamespace(
        destination_directory=destination,
        source_bin=Path("SRK-Diagnostics.bin"),
        source_cue=Path("SRK-Diagnostics.cue"),
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
    )
    return SimpleNamespace(
        plan=plan,
        batch_image_sha256=_IMAGE_SHA,
        deployable_bin_sha256=_BIN_SHA,
        deployable_cue_sha256=_CUE_SHA,
    )


def _deployment(card: Path, *, add_unrelated_change: bool = False, add_extra: bool = False):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R19"
    destination.mkdir()
    bin_path = destination / "SRK-Diagnostics.bin"
    cue_path = destination / "SRK-Diagnostics.cue"
    bin_path.write_bytes(_BIN)
    cue_path.write_bytes(_CUE)
    if add_extra:
        (destination / "SURPRISE.TXT").write_text("unexpected", encoding="utf-8")
    if add_unrelated_change:
        (card / "SAROO" / "saroocfg.txt").write_text("CHANGED\n", encoding="utf-8")
    plan = SimpleNamespace(destination_directory=destination)
    return SimpleNamespace(
        plan=plan,
        destination_bin=bin_path,
        destination_cue=cue_path,
        bin_sha256=_BIN_SHA,
        cue_sha256=_CUE_SHA,
    )


class SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentTests(unittest.TestCase):
    def test_allowed_paths_ignore_windows_long_vs_83_root_aliases(self):
        card_root = Path("C:/Users/Developer.ERIDU/AppData/Local/Temp/example/CARD")
        destination = Path(
            "C:/Users/DEVELO~1.ERI/AppData/Local/Temp/example/CARD/"
            "SAROO/ISO/TEST/SRK-Diagnostics-R19"
        )
        deployment = SimpleNamespace(
            plan=SimpleNamespace(destination_directory=destination),
            destination_bin=destination / "SRK-Diagnostics.bin",
            destination_cue=destination / "SRK-Diagnostics.cue",
        )

        self.assertEqual(
            set(_allowed_paths(card_root, deployment)),
            {
                "SAROO/ISO/TEST/SRK-Diagnostics-R19",
                "SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.bin",
                "SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.cue",
            },
        )

    def test_prepare_revalidates_r19_and_creates_off_card_exact_inventory_without_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r19-card-before.json"
            before = _snapshot(card)

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment."
                "inspect_midi_68k_silent_batch_physical_candidate_pre_media",
                return_value=_pre_media(card),
            ) as inspect:
                result = prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    manifest,
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

            self.assertEqual(_snapshot(card), before)
            self.assertTrue(manifest.is_file())
            self.assertTrue(result.exact_verification.valid)
            self.assertEqual(result.guard_inventory.manifest_path, manifest.resolve())
            inspect.assert_called_once()
            self.assertEqual(
                inspect.call_args.kwargs["expected_image_sha256"],
                _IMAGE_SHA,
            )

    def test_prepare_refuses_guard_manifest_on_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            with self.assertRaisesRegex(
                SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError,
                "outside",
            ):
                prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    card / "guard.json",
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )

    def test_apply_requires_r19_specific_confirmation_before_any_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            before = _snapshot(card)
            with self.assertRaisesRegex(
                SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError,
                "DEPLOY-R19-SILENT-BATCH-PROOF",
            ):
                apply_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    root / "missing.json",
                    expected_guard_manifest_sha256="0" * 64,
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                    confirmation="WRONG",
                )
            self.assertEqual(_snapshot(card), before)

    def test_apply_allows_only_exact_new_r19_directory_and_verified_bin_cue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r19-card-before.json"

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment."
                "inspect_midi_68k_silent_batch_physical_candidate_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    manifest,
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment."
                    "apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(card),
                ):
                    result = apply_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                        root / "candidate",
                        card,
                        manifest,
                        expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                        expected_image_sha256=_IMAGE_SHA,
                        expected_bin_sha256=_BIN_SHA,
                        expected_cue_sha256=_CUE_SHA,
                        destination_name="SRK-Diagnostics-R19",
                        category="TEST",
                        confirmation=CONFIRMATION_TOKEN,
                    )

            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual(
                set(result.allowed_changed_paths),
                {
                    "SAROO/ISO/TEST/SRK-Diagnostics-R19",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.bin",
                    "SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.cue",
                },
            )
            self.assertEqual(result.deployment.destination_bin.read_bytes(), _BIN)
            self.assertEqual(result.deployment.destination_cue.read_bytes(), _CUE)

    def test_unauthorised_change_fails_post_guard_and_rollback_never_deletes_unexpected_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            manifest = root / "r19-card-before.json"

            with patch(
                "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment."
                "inspect_midi_68k_silent_batch_physical_candidate_pre_media",
                return_value=_pre_media(card),
            ):
                prepared = prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                    root / "candidate",
                    card,
                    manifest,
                    expected_image_sha256=_IMAGE_SHA,
                    expected_bin_sha256=_BIN_SHA,
                    expected_cue_sha256=_CUE_SHA,
                    destination_name="SRK-Diagnostics-R19",
                    category="TEST",
                )
                with patch(
                    "rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_guarded_deployment."
                    "apply_saroo_standalone_image_deployment",
                    side_effect=lambda *args, **kwargs: _deployment(
                        card,
                        add_unrelated_change=True,
                        add_extra=True,
                    ),
                ):
                    with self.assertRaisesRegex(
                        SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError,
                        "unauthorised difference.*rollback not attempted",
                    ):
                        apply_midi_68k_silent_batch_physical_candidate_guarded_deployment(
                            root / "candidate",
                            card,
                            manifest,
                            expected_guard_manifest_sha256=prepared.guard_inventory.manifest_sha256,
                            expected_image_sha256=_IMAGE_SHA,
                            expected_bin_sha256=_BIN_SHA,
                            expected_cue_sha256=_CUE_SHA,
                            destination_name="SRK-Diagnostics-R19",
                            category="TEST",
                            confirmation=CONFIRMATION_TOKEN,
                        )

            destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R19"
            self.assertTrue((destination / "SURPRISE.TXT").is_file())
            self.assertTrue(destination.is_dir())


if __name__ == "__main__":
    unittest.main()
