"""Contracts for the read-only R25 RR16 whole-card guard PREPARE gate."""

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guard_prepare as _gate
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guard_prepare import (
    PREPARE_RECEIPT_SCHEMA,
    SaturnMidi68KR25RRCalibrationGuardPrepareError,
    prepare_saturn_midi_68k_r25_rr16_calibration_guard,
)


def _fake_pre(destination: Path):
    plan = SimpleNamespace(destination_directory=destination)
    return SimpleNamespace(
        project_root=Path("candidate"),
        baseline_root=Path("r24"),
        manifest_sha256=_gate._pre.ACCEPTED_R25_MANIFEST_SHA256,
        report_sha256=_gate._pre.ACCEPTED_R25_REPORT_SHA256,
        calibration_image_sha256=_gate._pre.ACCEPTED_R25_IMAGE_SHA256,
        candidate_main_sha256=_gate._pre.ACCEPTED_R25_MAIN_SHA256,
        candidate_menu_sha256=_gate._pre.ACCEPTED_R25_MENU_SHA256,
        runtime_after_sha256=_gate._pre.ACCEPTED_R25_RUNTIME_SHA256,
        proof_header_sha256=_gate._pre.ACCEPTED_R25_PROOF_HEADER_SHA256,
        proof_source_sha256=_gate._pre.ACCEPTED_R25_PROOF_SOURCE_SHA256,
        deployable_bin_sha256=_gate._pre.ACCEPTED_R25_BIN_SHA256,
        deployable_cue_sha256=_gate._pre.ACCEPTED_R25_CUE_SHA256,
        sector_count=_gate._pre.ACCEPTED_R25_SECTOR_COUNT,
        raw_bytes=_gate._pre.ACCEPTED_R25_RAW_BYTES,
        plan=plan,
    )


class SaturnMidi68KR25RRCalibrationGuardPrepareTests(unittest.TestCase):
    def test_guard_and_receipt_must_be_off_card_before_any_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            card.mkdir()
            with patch.object(_gate, "inspect_saturn_midi_68k_r25_rr_calibration_pre_media") as inspect:
                with self.assertRaisesRegex(
                    SaturnMidi68KR25RRCalibrationGuardPrepareError,
                    "must be stored outside",
                ):
                    prepare_saturn_midi_68k_r25_rr16_calibration_guard(
                        root / "candidate",
                        card,
                        card / "guard.json",
                        root / "receipt.json",
                        destination_name="SRK-Diagnostics-R25-RR16-CAL",
                        category="TEST",
                    )
                inspect.assert_not_called()

    def test_prepare_binds_exact_candidate_card_snapshot_and_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            card.mkdir()
            evidence = root / "evidence"
            manifest = evidence / "r25-card-inventory.json"
            receipt = evidence / "r25-prepare-receipt.json"
            destination = card / "saroo" / "ISO" / "TEST" / "SRK-Diagnostics-R25-RR16-CAL"
            pre = _fake_pre(destination)
            inventory = SimpleNamespace(
                card_root=card.resolve(),
                manifest_path=manifest.resolve(),
                manifest_sha256="5" * 64,
                file_count=123,
                directory_count=45,
                total_file_bytes=987654321,
                hashed_file_count=67,
            )
            verification = SimpleNamespace(valid=True, differences=())
            with patch.object(
                _gate,
                "inspect_saturn_midi_68k_r25_rr_calibration_pre_media",
                side_effect=[pre, pre],
            ) as inspect, patch.object(
                _gate, "create_saroo_card_inventory", return_value=inventory
            ) as create_inventory, patch.object(
                _gate, "verify_saroo_card_inventory", return_value=verification
            ) as verify_inventory:
                result = prepare_saturn_midi_68k_r25_rr16_calibration_guard(
                    root / "candidate",
                    card,
                    manifest,
                    receipt,
                    destination_name="SRK-Diagnostics-R25-RR16-CAL",
                    category="TEST",
                )

            self.assertEqual(inspect.call_count, 2)
            create_inventory.assert_called_once_with(card.resolve(), manifest.resolve())
            self.assertEqual(verify_inventory.call_count, 2)
            self.assertTrue(receipt.is_file())
            document = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(document["schema"], PREPARE_RECEIPT_SCHEMA)
            self.assertEqual(
                document["candidate"]["manifest_sha256"],
                _gate._pre.ACCEPTED_R25_MANIFEST_SHA256,
            )
            self.assertEqual(
                document["candidate"]["deployable_bin_sha256"],
                _gate._pre.ACCEPTED_R25_BIN_SHA256,
            )
            self.assertEqual(document["card_guard"]["manifest_sha256"], "5" * 64)
            self.assertEqual(document["future_deployment"]["category"], "TEST")
            self.assertEqual(
                document["future_deployment"]["destination_name"],
                "SRK-Diagnostics-R25-RR16-CAL",
            )
            self.assertTrue(document["future_deployment"]["destination_fresh_at_prepare"])
            self.assertTrue(document["policy"]["prepare_only"])
            self.assertFalse(document["policy"]["apply_available_in_this_module"])
            self.assertFalse(document["policy"]["saroo_writes"])
            self.assertFalse(document["policy"]["production_rr_selected"])
            payload = dict(document)
            recorded = payload.pop("receipt_sha256")
            self.assertEqual(sha256(_gate._payload_bytes(payload)).hexdigest(), recorded)
            self.assertEqual(result.receipt_sha256, recorded)

    def test_candidate_drift_is_rejected_before_inventory_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            card.mkdir()
            pre = _fake_pre(card / "saroo" / "ISO" / "TEST" / "fresh")
            pre.manifest_sha256 = "0" * 64
            with patch.object(
                _gate,
                "inspect_saturn_midi_68k_r25_rr_calibration_pre_media",
                return_value=pre,
            ), patch.object(_gate, "create_saroo_card_inventory") as create_inventory:
                with self.assertRaisesRegex(
                    SaturnMidi68KR25RRCalibrationGuardPrepareError,
                    "accepted R25 manifest changed",
                ):
                    prepare_saturn_midi_68k_r25_rr16_calibration_guard(
                        root / "candidate",
                        card,
                        root / "guard.json",
                        root / "receipt.json",
                        destination_name="fresh",
                        category="TEST",
                    )
                create_inventory.assert_not_called()

    def test_card_change_after_snapshot_fails_without_receipt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = root / "CARD"
            card.mkdir()
            receipt = root / "receipt.json"
            pre = _fake_pre(card / "saroo" / "ISO" / "TEST" / "fresh")
            inventory = SimpleNamespace(
                card_root=card.resolve(), manifest_path=(root / "guard.json").resolve(),
                manifest_sha256="6" * 64, file_count=1, directory_count=1,
                total_file_bytes=1, hashed_file_count=1,
            )
            ok = SimpleNamespace(valid=True, differences=())
            changed = SimpleNamespace(valid=False, differences=("added: saroo/unexpected.bin",))
            with patch.object(
                _gate,
                "inspect_saturn_midi_68k_r25_rr_calibration_pre_media",
                side_effect=[pre, pre],
            ), patch.object(
                _gate, "create_saroo_card_inventory", return_value=inventory
            ), patch.object(
                _gate, "verify_saroo_card_inventory", side_effect=[ok, changed]
            ):
                with self.assertRaisesRegex(
                    SaturnMidi68KR25RRCalibrationGuardPrepareError,
                    "final prepare whole-card guard mismatch",
                ):
                    prepare_saturn_midi_68k_r25_rr16_calibration_guard(
                        root / "candidate",
                        card,
                        root / "guard.json",
                        receipt,
                        destination_name="fresh",
                        category="TEST",
                    )
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()
