"""Tests for importing controller-generated SAROO Work RAM captures."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.capture import load_manifest, verify_capture
from rikai_kotoba.hardware.saturn.saroo.capture_ingest import (
    SAROO_WORK_RAM_SIZE,
    SarooCaptureIngestError,
    import_saroo_game_work_ram_high_capture,
    import_saroo_work_ram_captures,
)
from rikai_kotoba.tools.saroo_capture_import import main as import_main


class SarooCaptureIngestTests(unittest.TestCase):
    @staticmethod
    def _card(
        root: Path,
        *,
        low: bytes | None = None,
        high: bytes | None = None,
        game_high: bytes | None = None,
    ) -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        saroo.mkdir(parents=True)
        low_data = low if low is not None else bytes(SAROO_WORK_RAM_SIZE)
        high_data = high if high is not None else (b"\x01" + bytes(SAROO_WORK_RAM_SIZE - 2) + b"\x02")
        (saroo / "SRK_WRAML.BIN").write_bytes(low_data)
        (saroo / "SRK_WRAMH.BIN").write_bytes(high_data)
        if game_high is not None:
            (saroo / "SRK_GAME_WRAMH.BIN").write_bytes(game_high)
        return card

    def test_imports_both_regions_into_one_verified_off_card_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            low_before = (card / "SAROO" / "SRK_WRAML.BIN").read_bytes()
            high_before = (card / "SAROO" / "SRK_WRAMH.BIN").read_bytes()

            result = import_saroo_work_ram_captures(
                card,
                root / "captures",
                checkpoint="menu",
                session_label="test-hardware",
            )

            self.assertEqual((card / "SAROO" / "SRK_WRAML.BIN").read_bytes(), low_before)
            self.assertEqual((card / "SAROO" / "SRK_WRAMH.BIN").read_bytes(), high_before)
            self.assertTrue(verify_capture(result.artifact.directory).valid)
            manifest = load_manifest(result.artifact.directory)
            self.assertEqual(manifest["checkpoint"], "menu")
            self.assertEqual(manifest["session_label"], "test-hardware")
            self.assertEqual(len(manifest["regions"]), 2)
            self.assertEqual(manifest["regions"][0]["start_address"], 0x00200000)
            self.assertEqual(manifest["regions"][1]["start_address"], 0x06000000)

    def test_summaries_report_zero_and_live_ranges(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            high = bytearray(SAROO_WORK_RAM_SIZE)
            high[0x20] = 0x11
            high[0x1234] = 0x22
            card = self._card(root, high=bytes(high))

            result = import_saroo_work_ram_captures(card, root / "captures")
            low_summary, high_summary = result.summaries

            self.assertEqual(low_summary.nonzero_bytes, 0)
            self.assertIsNone(low_summary.first_nonzero_address)
            self.assertIsNone(low_summary.last_nonzero_address)
            self.assertEqual(high_summary.nonzero_bytes, 2)
            self.assertEqual(high_summary.first_nonzero_address, 0x06000020)
            self.assertEqual(high_summary.last_nonzero_address, 0x06001234)
            self.assertEqual(high_summary.sha256, sha256(bytes(high)).hexdigest())

    def test_rejects_wrong_sized_capture_without_publishing_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            (card / "SAROO" / "SRK_WRAMH.BIN").write_bytes(b"short")
            store = root / "captures"

            with self.assertRaisesRegex(SarooCaptureIngestError, "unexpected size"):
                import_saroo_work_ram_captures(card, store)

            self.assertFalse(store.exists())

    def test_rejects_capture_store_on_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)

            with self.assertRaisesRegex(SarooCaptureIngestError, "outside"):
                import_saroo_work_ram_captures(card, card / "captures")

    def test_module_command_imports_without_modifying_card(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = self._card(root)
            low_before = (card / "SAROO" / "SRK_WRAML.BIN").read_bytes()
            high_before = (card / "SAROO" / "SRK_WRAMH.BIN").read_bytes()

            exit_code = import_main(
                [
                    str(card),
                    "--store-root",
                    str(root / "captures"),
                    "--checkpoint",
                    "menu-test",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual((card / "SAROO" / "SRK_WRAML.BIN").read_bytes(), low_before)
            self.assertEqual((card / "SAROO" / "SRK_WRAMH.BIN").read_bytes(), high_before)
            artifacts = [path for path in (root / "captures").iterdir() if path.is_dir()]
            self.assertEqual(len(artifacts), 1)
            self.assertTrue(verify_capture(artifacts[0]).valid)

    def test_imports_one_shot_game_wramh_as_single_verified_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_high = bytearray(SAROO_WORK_RAM_SIZE)
            game_high[0x12002] = 0x55
            game_high[0xC8D2B] = 0xAA
            game_payload = bytes(game_high)
            card = self._card(root, game_high=game_payload)
            source = card / "SAROO" / "SRK_GAME_WRAMH.BIN"
            before = source.read_bytes()

            result = import_saroo_game_work_ram_high_capture(
                card,
                root / "captures",
                checkpoint="first-read-execution",
                session_label="game-test",
            )

            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(verify_capture(result.artifact.directory).valid)
            self.assertEqual(len(result.summaries), 1)
            summary = result.summaries[0]
            self.assertEqual(summary.sha256, sha256(game_payload).hexdigest())
            self.assertEqual(summary.first_nonzero_address, 0x06012002)
            self.assertEqual(summary.last_nonzero_address, 0x060C8D2B)
            manifest = load_manifest(result.artifact.directory)
            self.assertEqual(manifest["checkpoint"], "first-read-execution")
            self.assertEqual(manifest["session_label"], "game-test")
            self.assertEqual(len(manifest["regions"]), 1)
            self.assertEqual(manifest["regions"][0]["start_address"], 0x06000000)

    def test_module_command_game_wramh_mode_uses_title_neutral_default_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_payload = b"\x01" + bytes(SAROO_WORK_RAM_SIZE - 1)
            card = self._card(root, game_high=game_payload)
            source = card / "SAROO" / "SRK_GAME_WRAMH.BIN"
            before = source.read_bytes()

            exit_code = import_main(
                [
                    str(card),
                    "--store-root",
                    str(root / "captures"),
                    "--game-wramh",
                    "--session-label",
                    "first-game",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(source.read_bytes(), before)
            artifacts = [path for path in (root / "captures").iterdir() if path.is_dir()]
            self.assertEqual(len(artifacts), 1)
            self.assertTrue(verify_capture(artifacts[0]).valid)
            manifest = load_manifest(artifacts[0])
            self.assertEqual(manifest["checkpoint"], "saroo-ingame")
            self.assertEqual(manifest["session_label"], "first-game")
            self.assertEqual(len(manifest["regions"]), 1)


if __name__ == "__main__":
    unittest.main()
