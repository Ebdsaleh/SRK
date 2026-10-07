"""Synthetic tests for the read-only SAROO SD-card inventory guard."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SarooCardInventoryError,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from rikai_kotoba.tools.saroo_card_guard import main as guard_main


class SarooCardGuardTests(unittest.TestCase):
    @staticmethod
    def _card(root: Path) -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        iso = saroo / "ISO"
        iso.mkdir(parents=True)
        (saroo / "ssfirm.bin").write_bytes(b"firmware-baseline")
        (saroo / "mcuapp.bin").write_bytes(b"mcu")
        (saroo / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
        (iso / "GAME.CUE").write_text('FILE "GAME.BIN" BINARY\n', encoding="ascii")
        (iso / "GAME.BIN").write_bytes(b"0123456789abcdef")
        return card

    def test_snapshot_records_every_path_and_hashes_small_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"

            result = create_saroo_card_inventory(card, manifest, hash_max_bytes=8)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            entries = {item["path"]: item for item in document["entries"]}

            self.assertEqual(result.file_count, 5)
            self.assertEqual(result.directory_count, 2)
            self.assertIn("SAROO/ISO/GAME.BIN", entries)
            self.assertEqual(entries["SAROO/ISO/GAME.BIN"]["size"], 16)
            self.assertIsNone(entries["SAROO/ISO/GAME.BIN"]["sha256"])
            self.assertEqual(
                entries["SAROO/ssfirm.bin"]["sha256"],
                sha256(b"firmware-baseline").hexdigest(),
            )
            self.assertTrue(manifest.is_file())

    def test_snapshot_refuses_manifest_on_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            with self.assertRaisesRegex(SarooCardInventoryError, "outside"):
                create_saroo_card_inventory(card, card / "inventory.json")

    def test_snapshot_refuses_to_overwrite_existing_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            manifest.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(SarooCardInventoryError, "already exists"):
                create_saroo_card_inventory(card, manifest)
            self.assertEqual(manifest.read_text(encoding="utf-8"), "keep")

    def test_exact_verification_matches_unchanged_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            create_saroo_card_inventory(card, manifest, hash_max_bytes=8)

            verification = verify_saroo_card_inventory(card, manifest)

            self.assertTrue(verification.valid)
            self.assertEqual(verification.differences, ())

    def test_verification_detects_added_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            create_saroo_card_inventory(card, manifest)
            (card / "unexpected.bin").write_bytes(b"x")

            verification = verify_saroo_card_inventory(card, manifest)

            self.assertFalse(verification.valid)
            self.assertTrue(any("added:" in item for item in verification.differences))

    def test_verification_detects_missing_and_resized_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            create_saroo_card_inventory(card, manifest)
            (card / "SAROO" / "mcuapp.bin").unlink()
            (card / "SAROO" / "ISO" / "GAME.BIN").write_bytes(b"different-length-data")

            verification = verify_saroo_card_inventory(card, manifest)

            self.assertFalse(verification.valid)
            self.assertTrue(any("missing:" in item for item in verification.differences))
            self.assertTrue(any("size changed:" in item for item in verification.differences))

    def test_verification_detects_same_size_small_file_content_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            create_saroo_card_inventory(card, manifest)
            config = card / "SAROO" / "saroocfg.txt"
            before = config.read_bytes()
            config.write_bytes(b"X" * len(before))

            verification = verify_saroo_card_inventory(card, manifest)

            self.assertFalse(verification.valid)
            self.assertTrue(
                any("content hash changed:" in item for item in verification.differences)
            )

    def test_allowed_firmware_change_does_not_hide_other_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            create_saroo_card_inventory(card, manifest)
            (card / "SAROO" / "ssfirm.bin").write_bytes(b"new-firmware")

            allowed = verify_saroo_card_inventory(
                card,
                manifest,
                allowed_changed_paths=["SAROO/ssfirm.bin"],
            )
            self.assertTrue(allowed.valid)

            (card / "SAROO" / "mcuapp.bin").write_bytes(b"BAD")
            not_allowed = verify_saroo_card_inventory(
                card,
                manifest,
                allowed_changed_paths=["SAROO/ssfirm.bin"],
            )
            self.assertFalse(not_allowed.valid)

    def test_command_snapshot_and_verify_are_read_only_to_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            manifest = root / "inventory.json"
            before = {
                path.relative_to(card).as_posix(): path.read_bytes()
                for path in card.rglob("*")
                if path.is_file()
            }

            self.assertEqual(
                guard_main(["snapshot", str(card), str(manifest), "--hash-max-bytes", "8"]),
                0,
            )
            self.assertEqual(guard_main(["verify", str(card), str(manifest)]), 0)

            after = {
                path.relative_to(card).as_posix(): path.read_bytes()
                for path in card.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
