"""Synthetic tests for read-only SAROO firmware deployment planning."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    SarooDeploymentPlanError,
    plan_saroo_firmware_deployment,
)
from rikai_kotoba.tools.saroo_deployment import main as deployment_main


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


if __name__ == "__main__":
    unittest.main()
