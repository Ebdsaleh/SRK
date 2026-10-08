"""Synthetic tests for guarded transitions between accepted SAROO firmware builds."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.saroo.card_guard import create_saroo_card_inventory
from rikai_kotoba.hardware.saturn.saroo.deployment import (
    apply_saroo_firmware as raw_apply_saroo_firmware,
)
from rikai_kotoba.hardware.saturn.saroo.firmware_transition import (
    transition_saroo_firmware_guarded,
)
from rikai_kotoba.hardware.saturn.saroo.guarded_deployment import (
    SarooGuardedDeploymentError,
)
from rikai_kotoba.tools.saroo_transition import main as transition_main


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class SarooFirmwareTransitionTests(unittest.TestCase):
    @staticmethod
    def _card(root: Path, firmware: bytes) -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        iso = saroo / "ISO"
        iso.mkdir(parents=True)
        (saroo / "ssfirm.bin").write_bytes(firmware)
        (saroo / "mcuapp.bin").write_bytes(b"mcu")
        (saroo / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
        (iso / "GAME.BIN").write_bytes(b"game-data" * 256)
        return card

    @staticmethod
    def _baseline(root: Path, card: Path):
        manifest = root / "card-before.json"
        result = create_saroo_card_inventory(card, manifest, hash_max_bytes=64)
        return manifest, result.manifest_sha256

    def test_transition_accepts_only_preexisting_firmware_difference_and_preserves_current(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original-baseline"
            accepted = b"accepted-research-build"
            candidate_data = b"capture-menu-build"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            firmware = card / "SAROO" / "ssfirm.bin"
            firmware.write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)
            game_before = (card / "SAROO" / "ISO" / "GAME.BIN").read_bytes()

            result = transition_saroo_firmware_guarded(
                card,
                candidate,
                root / "backups",
                manifest,
                expected_guard_manifest_sha256=manifest_hash,
                expected_current_sha256=_sha(accepted),
                expected_candidate_sha256=_sha(candidate_data),
            )

            self.assertTrue(result.pre_guard_valid)
            self.assertTrue(result.post_guard_valid)
            self.assertEqual(firmware.read_bytes(), candidate_data)
            self.assertEqual(result.deployment.backup_path.read_bytes(), accepted)
            self.assertEqual((card / "SAROO" / "ISO" / "GAME.BIN").read_bytes(), game_before)

    def test_transition_blocks_unrelated_card_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            (card / "SAROO" / "ssfirm.bin").write_bytes(accepted)
            (card / "SAROO" / "ISO" / "unexpected.txt").write_text("x", encoding="utf-8")
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "whole-card guard mismatch"):
                transition_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_current_sha256=_sha(accepted),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), accepted)
            self.assertFalse((root / "backups").exists())

    def test_transition_rejects_wrong_current_firmware_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            (card / "SAROO" / "ssfirm.bin").write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "firmware hash mismatch"):
                transition_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_current_sha256=_sha(b"not-the-installed-build"),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), accepted)

    def test_post_transition_unrelated_mutation_rolls_firmware_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            firmware = card / "SAROO" / "ssfirm.bin"
            firmware.write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            def apply_then_mutate(*args, **kwargs):
                result = raw_apply_saroo_firmware(*args, **kwargs)
                config = card / "SAROO" / "saroocfg.txt"
                config.write_bytes(b"X" * len(config.read_bytes()))
                return result

            with patch(
                "rikai_kotoba.hardware.saturn.saroo.firmware_transition.apply_saroo_firmware",
                side_effect=apply_then_mutate,
            ):
                with self.assertRaisesRegex(SarooGuardedDeploymentError, "post-transition guard failed"):
                    transition_saroo_firmware_guarded(
                        card,
                        candidate,
                        root / "backups",
                        manifest,
                        expected_guard_manifest_sha256=manifest_hash,
                        expected_current_sha256=_sha(accepted),
                        expected_candidate_sha256=_sha(candidate_data),
                    )

            self.assertEqual(firmware.read_bytes(), accepted)

    def test_transition_command_wrong_confirmation_token_blocks_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            firmware = card / "SAROO" / "ssfirm.bin"
            firmware.write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            result = transition_main(
                [
                    str(card),
                    str(candidate),
                    "--backup-root",
                    str(root / "backups"),
                    "--guard-manifest",
                    str(manifest),
                    "--expected-guard-manifest-sha256",
                    manifest_hash,
                    "--expected-current-sha256",
                    _sha(accepted),
                    "--expected-candidate-sha256",
                    _sha(candidate_data),
                    "--confirm-transition",
                    "NO",
                ]
            )

            self.assertEqual(result, 2)
            self.assertEqual(firmware.read_bytes(), accepted)
            self.assertFalse((root / "backups").exists())

    def test_save_growth_remains_blocked_without_explicit_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            save = card / "SAROO" / "SS_SAVE.BIN"
            save.write_bytes(b"H" * 0x10000)
            manifest, manifest_hash = self._baseline(root, card)
            save.write_bytes(save.read_bytes() + b"S" * 0x10000)
            (card / "SAROO" / "ssfirm.bin").write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "whole-card guard mismatch"):
                transition_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_current_sha256=_sha(accepted),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), accepted)
            self.assertFalse((root / "backups").exists())

    def test_exact_reviewed_save_is_preserved_and_required_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            save = card / "SAROO" / "SS_SAVE.BIN"
            save.write_bytes(b"H" * 0x10000)
            manifest, manifest_hash = self._baseline(root, card)
            reviewed_save = b"H" * 0x10000 + b"S" * 0x10000
            save.write_bytes(reviewed_save)
            (card / "SAROO" / "ssfirm.bin").write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)
            backup_root = root / "backups"

            result = transition_saroo_firmware_guarded(
                card,
                candidate,
                backup_root,
                manifest,
                expected_guard_manifest_sha256=manifest_hash,
                expected_current_sha256=_sha(accepted),
                expected_candidate_sha256=_sha(candidate_data),
                expected_ss_save_sha256=_sha(reviewed_save),
                expected_ss_save_size=len(reviewed_save),
            )

            self.assertTrue(result.pre_guard_valid)
            self.assertTrue(result.post_guard_valid)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), candidate_data)
            self.assertEqual(save.read_bytes(), reviewed_save)
            self.assertEqual(result.reviewed_save_sha256, _sha(reviewed_save))
            self.assertEqual(result.reviewed_save_size, len(reviewed_save))
            self.assertIsNotNone(result.reviewed_save_backup_path)
            self.assertEqual(result.reviewed_save_backup_path.read_bytes(), reviewed_save)
            self.assertTrue(result.reviewed_save_backup_path.name.startswith("SS_SAVE_"))

    def test_wrong_reviewed_save_hash_blocks_before_any_backup_or_card_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            save = card / "SAROO" / "SS_SAVE.BIN"
            save.write_bytes(b"H" * 0x10000)
            manifest, manifest_hash = self._baseline(root, card)
            reviewed_save = b"H" * 0x10000 + b"S" * 0x10000
            save.write_bytes(reviewed_save)
            firmware = card / "SAROO" / "ssfirm.bin"
            firmware.write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "SS_SAVE.BIN hash mismatch"):
                transition_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_current_sha256=_sha(accepted),
                    expected_candidate_sha256=_sha(candidate_data),
                    expected_ss_save_sha256=_sha(b"wrong"),
                    expected_ss_save_size=len(reviewed_save),
                )

            self.assertEqual(firmware.read_bytes(), accepted)
            self.assertEqual(save.read_bytes(), reviewed_save)
            self.assertFalse((root / "backups").exists())

    def test_transition_command_requires_complete_reviewed_save_expectation_pair(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"candidate"
            card = self._card(root, original)
            manifest, manifest_hash = self._baseline(root, card)
            firmware = card / "SAROO" / "ssfirm.bin"
            firmware.write_bytes(accepted)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            result = transition_main(
                [
                    str(card),
                    str(candidate),
                    "--backup-root",
                    str(root / "backups"),
                    "--guard-manifest",
                    str(manifest),
                    "--expected-guard-manifest-sha256",
                    manifest_hash,
                    "--expected-current-sha256",
                    _sha(accepted),
                    "--expected-candidate-sha256",
                    _sha(candidate_data),
                    "--expected-ss-save-sha256",
                    _sha(b"save"),
                    "--confirm-transition",
                    "TRANSITION-SSFIRM",
                ]
            )

            self.assertEqual(result, 2)
            self.assertEqual(firmware.read_bytes(), accepted)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
