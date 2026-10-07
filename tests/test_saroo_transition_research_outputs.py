"""Guard behavior when SRK's own Work RAM files exist on the research card."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.card_guard import create_saroo_card_inventory
from rikai_kotoba.hardware.saturn.saroo.firmware_transition import (
    transition_saroo_firmware_guarded,
)
from rikai_kotoba.hardware.saturn.saroo.guarded_deployment import SarooGuardedDeploymentError


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


class SarooTransitionResearchOutputTests(unittest.TestCase):
    @staticmethod
    def _card(root: Path, firmware: bytes) -> Path:
        card = root / "CARD"
        saroo = card / "SAROO"
        iso = saroo / "ISO"
        iso.mkdir(parents=True)
        (saroo / "ssfirm.bin").write_bytes(firmware)
        (saroo / "mcuapp.bin").write_bytes(b"mcu")
        (saroo / "saroocfg.txt").write_text("[global]\n", encoding="utf-8")
        (iso / "GAME.BIN").write_bytes(b"game" * 256)
        return card

    def test_valid_one_mib_capture_outputs_do_not_block_next_transition(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"next"
            card = self._card(root, original)
            manifest = root / "baseline.json"
            manifest_result = create_saroo_card_inventory(card, manifest, hash_max_bytes=64)
            saroo = card / "SAROO"
            (saroo / "ssfirm.bin").write_bytes(accepted)
            (saroo / "SRK_WRAML.BIN").write_bytes(bytes(0x100000))
            (saroo / "SRK_WRAMH.BIN").write_bytes(b"\x01" + bytes(0x0fffff))
            (saroo / "SRK_GAME_WRAMH.BIN").write_bytes(b"\x02" + bytes(0x0fffff))
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            result = transition_saroo_firmware_guarded(
                card,
                candidate,
                root / "backups",
                manifest,
                expected_guard_manifest_sha256=manifest_result.manifest_sha256,
                expected_current_sha256=_sha(accepted),
                expected_candidate_sha256=_sha(candidate_data),
            )

            self.assertTrue(result.pre_guard_valid)
            self.assertTrue(result.post_guard_valid)
            self.assertEqual((saroo / "ssfirm.bin").read_bytes(), candidate_data)
            self.assertEqual((saroo / "SRK_WRAML.BIN").stat().st_size, 0x100000)
            self.assertEqual((saroo / "SRK_WRAMH.BIN").stat().st_size, 0x100000)
            self.assertEqual((saroo / "SRK_GAME_WRAMH.BIN").stat().st_size, 0x100000)

    def test_wrong_sized_capture_output_blocks_transition(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            original = b"original"
            accepted = b"accepted"
            candidate_data = b"next"
            card = self._card(root, original)
            manifest = root / "baseline.json"
            manifest_result = create_saroo_card_inventory(card, manifest, hash_max_bytes=64)
            saroo = card / "SAROO"
            (saroo / "ssfirm.bin").write_bytes(accepted)
            (saroo / "SRK_GAME_WRAMH.BIN").write_bytes(b"short")
            candidate = root / "candidate.bin"
            candidate.write_bytes(candidate_data)

            with self.assertRaisesRegex(SarooGuardedDeploymentError, "unexpected size"):
                transition_saroo_firmware_guarded(
                    card,
                    candidate,
                    root / "backups",
                    manifest,
                    expected_guard_manifest_sha256=manifest_result.manifest_sha256,
                    expected_current_sha256=_sha(accepted),
                    expected_candidate_sha256=_sha(candidate_data),
                )

            self.assertEqual((saroo / "ssfirm.bin").read_bytes(), accepted)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
