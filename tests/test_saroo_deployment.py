"""Synthetic tests for preserve-first SAROO firmware deployment."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    SarooDeploymentApplyError,
    SarooDeploymentPlanError,
    SarooDeploymentRestoreError,
    apply_saroo_firmware,
    plan_saroo_firmware_deployment,
    restore_saroo_firmware,
)
from rikai_kotoba.tools.saroo_apply import main as apply_main
from rikai_kotoba.tools.saroo_deployment import main as deployment_main
from rikai_kotoba.tools.saroo_restore import main as restore_main


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class SarooDeploymentPlanTests(unittest.TestCase):
    @staticmethod
    def _modern_card(root: Path, data: bytes = b"known-good-card") -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        saroo.mkdir(parents=True)
        (saroo / "ssfirm.bin").write_bytes(data)
        (saroo / "mcuapp.bin").write_bytes(b"mcu")
        (saroo / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
        (saroo / "ISO").mkdir()
        return card

    def test_modern_plan_is_read_only_and_content_addresses_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = self._modern_card(root, current)
            candidate = root / "candidate" / "ssfirm.bin"
            candidate.parent.mkdir()
            candidate.write_bytes(b"new-srk-build")
            backup_root = root / "backups"

            before = (card / "SAROO" / "ssfirm.bin").read_bytes()
            before_entries = sorted(path.relative_to(card) for path in card.rglob("*"))

            plan = plan_saroo_firmware_deployment(card, candidate, backup_root)

            self.assertTrue(plan.ready_for_future_apply)
            self.assertTrue(plan.replacement_needed)
            self.assertEqual(plan.layout, "modern")
            self.assertEqual(plan.destination_relative_path, "SAROO/ssfirm.bin")
            self.assertEqual(plan.existing_firmware.sha256, _sha(current))
            self.assertEqual(plan.candidate.sha256, _sha(b"new-srk-build"))
            self.assertEqual(
                plan.backup_path,
                backup_root.resolve() / f"ssfirm_{_sha(current)[:16]}.bin",
            )
            self.assertFalse(plan.backup_already_valid)
            self.assertFalse(backup_root.exists())
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), before)
            self.assertEqual(
                sorted(path.relative_to(card) for path in card.rglob("*")),
                before_entries,
            )

    def test_identical_candidate_requires_no_replacement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = b"same"
            card = self._modern_card(root, data)
            candidate = root / "ssfirm.bin"
            candidate.write_bytes(data)

            plan = plan_saroo_firmware_deployment(card, candidate, root / "backups")

            self.assertFalse(plan.replacement_needed)
            self.assertFalse(plan.ready_for_future_apply)
            self.assertTrue(any("byte-identical" in warning for warning in plan.warnings))

    def test_legacy_layout_is_not_authorised_for_apply(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            card.mkdir()
            (card / "ramimage.bin").write_bytes(b"legacy")
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")

            plan = plan_saroo_firmware_deployment(card, candidate, root / "backups")

            self.assertEqual(plan.layout, "legacy")
            self.assertFalse(plan.ready_for_future_apply)
            self.assertIsNone(plan.destination_relative_path)
            self.assertIsNone(plan.backup_path)

    def test_candidate_on_card_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._modern_card(root)
            candidate = card / "candidate.bin"
            candidate.write_bytes(b"candidate")

            with self.assertRaisesRegex(SarooDeploymentPlanError, "outside"):
                plan_saroo_firmware_deployment(card, candidate, root / "backups")

    def test_backup_root_on_card_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._modern_card(root)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")

            with self.assertRaisesRegex(SarooDeploymentPlanError, "backup root"):
                plan_saroo_firmware_deployment(card, candidate, card / "backup")

    def test_conflicting_existing_backup_blocks_future_apply(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")
            backup_root = root / "backups"
            backup_root.mkdir()
            expected = backup_root / f"ssfirm_{_sha(current)[:16]}.bin"
            expected.write_bytes(b"different-content")

            plan = plan_saroo_firmware_deployment(card, candidate, backup_root)

            self.assertFalse(plan.ready_for_future_apply)
            self.assertFalse(plan.backup_already_valid)
            self.assertTrue(any("different content" in warning for warning in plan.warnings))
            self.assertEqual(expected.read_bytes(), b"different-content")

    def test_matching_existing_backup_is_recognised(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")
            backup_root = root / "backups"
            backup_root.mkdir()
            expected = backup_root / f"ssfirm_{_sha(current)[:16]}.bin"
            expected.write_bytes(current)

            plan = plan_saroo_firmware_deployment(card, candidate, backup_root)

            self.assertTrue(plan.ready_for_future_apply)
            self.assertTrue(plan.backup_already_valid)
            self.assertEqual(expected.read_bytes(), current)

    def test_command_prints_plan_without_creating_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._modern_card(root)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")
            backup_root = root / "backups"

            result = deployment_main(
                [str(card), str(candidate), "--backup-root", str(backup_root)]
            )

            self.assertEqual(result, 0)
            self.assertFalse(backup_root.exists())
            self.assertEqual(
                (card / "SAROO" / "ssfirm.bin").read_bytes(),
                b"known-good-card",
            )

    def test_apply_creates_verified_backup_then_replaces_only_ssfirm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            new = b"new-srk-build"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(new)
            backup_root = root / "backups"
            mcu_before = (card / "SAROO" / "mcuapp.bin").read_bytes()
            config_before = (card / "SAROO" / "saroocfg.txt").read_bytes()

            result = apply_saroo_firmware(
                card,
                candidate,
                backup_root,
                expected_existing_sha256=_sha(current),
                expected_candidate_sha256=_sha(new),
            )

            self.assertFalse(result.backup_reused)
            self.assertEqual(result.backup_path.read_bytes(), current)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), new)
            self.assertEqual((card / "SAROO" / "mcuapp.bin").read_bytes(), mcu_before)
            self.assertEqual((card / "SAROO" / "saroocfg.txt").read_bytes(), config_before)
            self.assertFalse((card / "SAROO" / "ssfirm.bin.srk-new").exists())

    def test_apply_reuses_matching_verified_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            new = b"candidate"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(new)
            backup_root = root / "backups"
            backup_root.mkdir()
            backup = backup_root / f"ssfirm_{_sha(current)[:16]}.bin"
            backup.write_bytes(current)

            result = apply_saroo_firmware(
                card,
                candidate,
                backup_root,
                expected_existing_sha256=_sha(current),
                expected_candidate_sha256=_sha(new),
            )

            self.assertTrue(result.backup_reused)
            self.assertEqual(backup.read_bytes(), current)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), new)

    def test_apply_stale_existing_hash_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"changed-card"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"candidate")
            backup_root = root / "backups"

            with self.assertRaisesRegex(SarooDeploymentApplyError, "existing card firmware hash"):
                apply_saroo_firmware(
                    card,
                    candidate,
                    backup_root,
                    expected_existing_sha256=_sha(b"older-card"),
                    expected_candidate_sha256=_sha(b"candidate"),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)
            self.assertFalse(backup_root.exists())

    def test_apply_stale_candidate_hash_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(b"changed-candidate")
            backup_root = root / "backups"

            with self.assertRaisesRegex(SarooDeploymentApplyError, "candidate firmware hash"):
                apply_saroo_firmware(
                    card,
                    candidate,
                    backup_root,
                    expected_existing_sha256=_sha(current),
                    expected_candidate_sha256=_sha(b"older-candidate"),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)
            self.assertFalse(backup_root.exists())

    def test_restore_preserves_current_candidate_then_restores_baseline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline = b"known-good-card"
            candidate_data = b"new-srk-build"
            card = self._modern_card(root, candidate_data)
            backup = root / "backups" / "baseline.bin"
            backup.parent.mkdir()
            backup.write_bytes(baseline)

            result = restore_saroo_firmware(
                card,
                backup,
                expected_current_sha256=_sha(candidate_data),
                expected_backup_sha256=_sha(baseline),
            )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), baseline)
            self.assertEqual(result.pre_restore_archive_path.read_bytes(), candidate_data)
            self.assertEqual(result.restored_sha256, _sha(baseline))
            self.assertFalse(result.archive_reused)

    def test_restore_stale_current_hash_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"unexpected-current"
            baseline = b"baseline"
            card = self._modern_card(root, current)
            backup = root / "backup.bin"
            backup.write_bytes(baseline)

            with self.assertRaisesRegex(SarooDeploymentRestoreError, "current card firmware hash"):
                restore_saroo_firmware(
                    card,
                    backup,
                    expected_current_sha256=_sha(b"expected-candidate"),
                    expected_backup_sha256=_sha(baseline),
                )

            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)

    def test_apply_command_requires_exact_confirmation_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            new = b"candidate"
            card = self._modern_card(root, current)
            candidate = root / "candidate.bin"
            candidate.write_bytes(new)
            backup_root = root / "backups"

            result = apply_main(
                [
                    str(card),
                    str(candidate),
                    "--backup-root",
                    str(backup_root),
                    "--expected-existing-sha256",
                    _sha(current),
                    "--expected-candidate-sha256",
                    _sha(new),
                    "--confirm-write",
                    "NO",
                ]
            )

            self.assertEqual(result, 2)
            self.assertFalse(backup_root.exists())
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)

    def test_restore_command_requires_exact_confirmation_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"candidate"
            baseline = b"baseline"
            card = self._modern_card(root, current)
            backup = root / "backup.bin"
            backup.write_bytes(baseline)

            result = restore_main(
                [
                    str(card),
                    str(backup),
                    "--expected-current-sha256",
                    _sha(current),
                    "--expected-backup-sha256",
                    _sha(baseline),
                    "--confirm-restore",
                    "NO",
                ]
            )

            self.assertEqual(result, 2)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)


if __name__ == "__main__":
    unittest.main()
