"""Synthetic tests for whole-card guarded SAROO firmware writes."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    create_saroo_card_inventory,
)
from rikai_kotoba.hardware.saturn.saroo.deployment import (
    apply_saroo_firmware as raw_apply_saroo_firmware,
)
from rikai_kotoba.hardware.saturn.saroo.guarded_deployment import (
    SarooGuardedDeploymentError,
    apply_saroo_firmware_guarded,
    restore_saroo_firmware_guarded,
)
from rikai_kotoba.tools.saroo_apply import main as apply_main


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class SarooGuardedDeploymentTests(unittest.TestCase):
    @staticmethod
    def _modern_card(root: Path, firmware: bytes = b"baseline") -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        iso = saroo / "ISO"
        iso.mkdir(parents=True)
        (saroo / "ssfirm.bin").write_bytes(firmware)
        (saroo / "mcuapp.bin").write_bytes(b"mcu")
        (saroo / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
        (iso / "GAME.CUE").write_text('FILE "GAME.BIN" BINARY\n', encoding="ascii")
        (iso / "GAME.BIN").write_bytes(b"game-data" * 256)
        return card

    @staticmethod
    def _baseline(root: Path, card: Path):
        manifest = root / "card-before.json"
        result = create_saroo_card_inventory(card, manifest, hash_max_bytes=64)
        return manifest, result.manifest_sha256

    def test_guarded_apply_requires_exact_whole_card_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate"
            card = self._modern_card(root, baseline)
            manifest, manifest_hash = self._baseline(root, card)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)
            (card / "unexpected.txt").write_text("new", encoding="utf-8")

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "whole-card guard mismatch"):
                apply_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_existing_sha256=_sha(baseline),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)
            self.assertFalse((root / "backups").exists())

    def test_guarded_apply_rejects_unreviewed_manifest_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate"
            card = self._modern_card(root, baseline)
            manifest, _manifest_hash = self._baseline(root, card)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "manifest hash"):
                apply_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256="0" * 64,
                    expected_existing_sha256=_sha(baseline),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)

    def test_guarded_apply_changes_only_ssfirm_and_post_guard_matches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate-build"
            card = self._modern_card(root, baseline)
            manifest, manifest_hash = self._baseline(root, card)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)
            game_before = (card / "SAROO" / "ISO" / "GAME.BIN").read_bytes()

            result = apply_saroo_firmware_guarded(
                card,
                candidate,
                root / "backups",
                manifest,
                expected_guard_manifest_sha256=manifest_hash,
                expected_existing_sha256=_sha(baseline),
                expected_candidate_sha256=_sha(candidate_data),
            )

            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), candidate_data)
            self.assertEqual((card / "SAROO" / "ISO" / "GAME.BIN").read_bytes(), game_before)
            self.assertEqual(result.deployment.backup_path.read_bytes(), baseline)

    def test_guarded_apply_reports_unrelated_post_write_change_and_restores_firmware(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate-build"
            card = self._modern_card(root, baseline)
            manifest, manifest_hash = self._baseline(root, card)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            def apply_then_mutate(*args, **kwargs):
                result = raw_apply_saroo_firmware(*args, **kwargs)
                config = card / "SAROO" / "saroocfg.txt"
                config.write_bytes(b"X" * len(config.read_bytes()))
                return result

            with patch(
                "rikai_kotoba.hardware.saturn.saroo.guarded_deployment.apply_saroo_firmware",
                side_effect=apply_then_mutate,
            ):
                with self.assertRaisesRegex(
                    SarooGuardedDeploymentError,
                    "post-apply whole-card guard failed",
                ):
                    apply_saroo_firmware_guarded(
                        card,
                        candidate,
                        root / "backups",
                        manifest,
                        expected_guard_manifest_sha256=manifest_hash,
                        expected_existing_sha256=_sha(baseline),
                        expected_candidate_sha256=_sha(candidate_data),
                    )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)

    def test_guarded_restore_allows_candidate_only_then_restores_exact_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate-build"
            card = self._modern_card(root, baseline)
            manifest, manifest_hash = self._baseline(root, card)
            backup = root / "backups" / "baseline.bin"
            backup.parent.mkdir()
            backup.write_bytes(baseline)
            (card / "SAROO" / "ssfirm.bin").write_bytes(candidate_data)

            result = restore_saroo_firmware_guarded(
                card,
                backup,
                manifest,
                expected_guard_manifest_sha256=manifest_hash,
                expected_current_sha256=_sha(candidate_data),
                expected_backup_sha256=_sha(baseline),
            )

            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)
            self.assertEqual(result.deployment.pre_restore_archive_path.read_bytes(), candidate_data)

    def test_guarded_restore_blocks_unrelated_card_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate-build"
            card = self._modern_card(root, baseline)
            manifest, manifest_hash = self._baseline(root, card)
            backup = root / "backup.bin"
            backup.write_bytes(baseline)
            (card / "SAROO" / "ssfirm.bin").write_bytes(candidate_data)
            (card / "SAROO" / "ISO" / "EXTRA.TXT").write_text("unexpected", encoding="utf-8")

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "whole-card guard mismatch"):
                restore_saroo_firmware_guarded(
                    card,
                    backup,
                    manifest,
                    expected_guard_manifest_sha256=manifest_hash,
                    expected_current_sha256=_sha(candidate_data),
                    expected_backup_sha256=_sha(baseline),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), candidate_data)

    def test_apply_command_blocks_write_when_guard_arguments_are_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"baseline"
            candidate_data = b"candidate"
            card = self._modern_card(root, baseline)
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            result = apply_main(
                [
                    str(card),
                    str(candidate),
                    "--backup-root",
                    str(root / "backups"),
                    "--expected-existing-sha256",
                    _sha(baseline),
                    "--expected-candidate-sha256",
                    _sha(candidate_data),
                    "--confirm-write",
                    "APPLY-SSFIRM",
                ]
            )

            self.assertEqual(result, 2)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
