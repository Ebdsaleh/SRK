"""Synthetic tests for standalone SAROO baseline backup."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    SarooDeploymentBackupError,
    backup_saroo_firmware,
)
from rikai_kotoba.tools.saroo_backup import main as backup_main


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _modern_card(root: Path, data: bytes) -> Path:
    card = root / "CARD"
    saroo = card / "SAROO"
    saroo.mkdir(parents=True)
    (saroo / "ssfirm.bin").write_bytes(data)
    (saroo / "mcuapp.bin").write_bytes(b"mcu")
    return card


class SarooDeploymentBackupTests(unittest.TestCase):
    def test_creates_verified_off_card_backup_without_modifying_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = _modern_card(root, current)
            backup_root = root / "backups"
            before = (card / "SAROO" / "ssfirm.bin").read_bytes()

            result = backup_saroo_firmware(
                card,
                backup_root,
                expected_existing_sha256=_sha(current),
            )

            self.assertFalse(result.backup_reused)
            self.assertEqual(result.firmware_sha256, _sha(current))
            self.assertEqual(result.backup_path.read_bytes(), current)
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), before)

    def test_reuses_matching_backup_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = _modern_card(root, current)
            backup_root = root / "backups"
            backup_root.mkdir()
            backup = backup_root / f"ssfirm_{_sha(current)[:16]}.bin"
            backup.write_bytes(current)

            result = backup_saroo_firmware(
                card,
                backup_root,
                expected_existing_sha256=_sha(current),
            )

            self.assertTrue(result.backup_reused)
            self.assertEqual(backup.read_bytes(), current)

    def test_stale_expected_hash_fails_before_creating_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = _modern_card(root, current)
            backup_root = root / "backups"

            with self.assertRaisesRegex(SarooDeploymentBackupError, "does not match"):
                backup_saroo_firmware(
                    card,
                    backup_root,
                    expected_existing_sha256=_sha(b"stale"),
                )

            self.assertFalse(backup_root.exists())
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)

    def test_command_creates_backup_and_leaves_card_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = b"known-good-card"
            card = _modern_card(root, current)
            backup_root = root / "backups"

            result = backup_main(
                [
                    str(card),
                    "--backup-root",
                    str(backup_root),
                    "--expected-existing-sha256",
                    _sha(current),
                ]
            )

            self.assertEqual(result, 0)
            self.assertEqual(
                (backup_root / f"ssfirm_{_sha(current)[:16]}.bin").read_bytes(),
                current,
            )
            self.assertEqual((card / "SAROO" / "ssfirm.bin").read_bytes(), current)


if __name__ == "__main__":
    unittest.main()
