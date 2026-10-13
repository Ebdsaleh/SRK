"""Regression tests for the explicit R25 RR16 guarded APPLY."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn.saroo.card_guard import create_saroo_card_inventory
from rikai_kotoba.hardware.saturn import midi_68k_r25_rr_calibration_guard_prepare as prepare_mod
from rikai_kotoba.hardware.saturn import midi_68k_r25_rr_calibration_pre_media_gate as pre_mod
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guarded_apply import (
    ACCEPTED_GUARD_MANIFEST_SHA256,
    ACCEPTED_PREPARE_RECEIPT_SHA256,
    CONFIRMATION_TOKEN,
    SaturnMidi68KR25RRCalibrationGuardedApplyError,
    _allowed_paths,
    _review_prepare_evidence,
    _safe_rollback_new_directory,
    apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment,
)

_BIN = b"R25-RR16-BIN"
_CUE = b"R25-RR16-CUE"


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
    return {
        p.relative_to(card).as_posix(): p.read_bytes() if p.is_file() else None
        for p in sorted(card.rglob("*"), key=lambda item: str(item).casefold())
    }


def _pre_media(root: Path, card: Path):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R25-RR16-CAL"
    return SimpleNamespace(
        project_root=(root / "candidate").resolve(),
        baseline_root=(root / "r24").resolve(),
        manifest_sha256=pre_mod.ACCEPTED_R25_MANIFEST_SHA256,
        report_sha256=pre_mod.ACCEPTED_R25_REPORT_SHA256,
        calibration_image_sha256=pre_mod.ACCEPTED_R25_IMAGE_SHA256,
        candidate_main_sha256=pre_mod.ACCEPTED_R25_MAIN_SHA256,
        candidate_menu_sha256=pre_mod.ACCEPTED_R25_MENU_SHA256,
        runtime_after_sha256=pre_mod.ACCEPTED_R25_RUNTIME_SHA256,
        proof_header_sha256=pre_mod.ACCEPTED_R25_PROOF_HEADER_SHA256,
        proof_source_sha256=pre_mod.ACCEPTED_R25_PROOF_SOURCE_SHA256,
        deployable_bin_sha256=pre_mod.ACCEPTED_R25_BIN_SHA256,
        deployable_cue_sha256=pre_mod.ACCEPTED_R25_CUE_SHA256,
        sector_count=pre_mod.ACCEPTED_R25_SECTOR_COUNT,
        raw_bytes=pre_mod.ACCEPTED_R25_RAW_BYTES,
        plan=SimpleNamespace(destination_directory=destination),
    )


def _evidence(root: Path, card: Path):
    guard = root / "guard.json"
    receipt = root / "receipt.json"
    inventory = create_saroo_card_inventory(card, guard)
    pre_media = _pre_media(root, card)
    payload = prepare_mod._receipt_payload(
        pre_media=pre_media,
        inventory=inventory,
        category="TEST",
        destination_name="SRK-Diagnostics-R25-RR16-CAL",
    )
    receipt_sha = prepare_mod._publish_receipt(receipt, payload)
    return guard, receipt, inventory, receipt_sha, pre_media


@contextmanager
def _accepted_fixture(inventory, receipt_sha):
    base = "rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guarded_apply."
    with (
        patch(base + "ACCEPTED_GUARD_MANIFEST_SHA256", inventory.manifest_sha256),
        patch(base + "ACCEPTED_PREPARE_RECEIPT_SHA256", receipt_sha),
        patch(base + "ACCEPTED_CARD_FILE_COUNT", inventory.file_count),
        patch(base + "ACCEPTED_CARD_DIRECTORY_COUNT", inventory.directory_count),
        patch(base + "ACCEPTED_CARD_TOTAL_FILE_BYTES", inventory.total_file_bytes),
        patch(base + "ACCEPTED_CARD_HASHED_FILE_COUNT", inventory.hashed_file_count),
    ):
        yield


def _deployment(card: Path):
    destination = card / "SAROO" / "ISO" / "TEST" / "SRK-Diagnostics-R25-RR16-CAL"
    destination.mkdir()
    bin_path = destination / "SRK-Diagnostics.bin"
    cue_path = destination / "SRK-Diagnostics.cue"
    bin_path.write_bytes(_BIN)
    cue_path.write_bytes(_CUE)
    return SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=bin_path,
        destination_cue=cue_path,
        bin_sha256=pre_mod.ACCEPTED_R25_BIN_SHA256,
        cue_sha256=pre_mod.ACCEPTED_R25_CUE_SHA256,
    )


class SaturnMidi68KR25RRCalibrationGuardedApplyTests(unittest.TestCase):
    def test_physical_prepare_anchors_are_pinned(self):
        self.assertEqual(ACCEPTED_GUARD_MANIFEST_SHA256, "5c17df50023c47955b4814eea648a506b3c30dafaa50ebfa157de65cffb9eac6")
        self.assertEqual(ACCEPTED_PREPARE_RECEIPT_SHA256, "c78b7702f0ed27af0a0f0d42baa4d5754b102adfd1bb148055fb7be960980f6f")

    def test_confirmation_token_is_r25_specific(self):
        self.assertEqual(CONFIRMATION_TOKEN, "DEPLOY-R25-RR16-CALIBRATION")

    def test_allowed_paths_are_exact(self):
        destination = Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL")
        deployment = SimpleNamespace(
            plan=SimpleNamespace(destination_directory=destination),
            destination_bin=destination / "SRK-Diagnostics.bin",
            destination_cue=destination / "SRK-Diagnostics.cue",
        )
        self.assertEqual(
            set(_allowed_paths(deployment)),
            {
                "saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL",
                "saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL/SRK-Diagnostics.bin",
                "saroo/ISO/TEST/SRK-Diagnostics-R25-RR16-CAL/SRK-Diagnostics.cue",
            },
        )

    def test_wrong_confirmation_stops_before_evidence_or_media_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            before = _snapshot(card)
            with self.assertRaisesRegex(SaturnMidi68KR25RRCalibrationGuardedApplyError, CONFIRMATION_TOKEN):
                apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment(
                    root / "candidate", card, root / "missing.json", root / "missing2.json",
                    destination_name="SRK-Diagnostics-R25-RR16-CAL", category="TEST", confirmation="WRONG",
                )
            self.assertEqual(_snapshot(card), before)

    def test_receipt_tamper_fails_canonical_digest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            guard, receipt, inventory, receipt_sha, _ = _evidence(root, card)
            document = json.loads(receipt.read_text(encoding="utf-8"))
            document["future_deployment"]["destination_name"] = "TAMPERED"
            receipt.write_text(json.dumps(document), encoding="utf-8")
            with _accepted_fixture(inventory, receipt_sha):
                with self.assertRaisesRegex(SaturnMidi68KR25RRCalibrationGuardedApplyError, "canonical content digest"):
                    _review_prepare_evidence(
                        card, (root / "candidate").resolve(), guard, receipt,
                        destination_name="SRK-Diagnostics-R25-RR16-CAL", category="TEST",
                    )

    def test_reviewed_apply_authorizes_only_new_r25_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            guard, receipt, inventory, receipt_sha, pre_media = _evidence(root, card)
            base = "rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guarded_apply."
            with (
                _accepted_fixture(inventory, receipt_sha),
                patch(base + "inspect_saturn_midi_68k_r25_rr_calibration_pre_media", return_value=pre_media),
                patch(base + "apply_saroo_standalone_image_deployment", side_effect=lambda *a, **k: _deployment(card)),
            ):
                result = apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment(
                    root / "candidate", card, guard, receipt,
                    destination_name="SRK-Diagnostics-R25-RR16-CAL", category="TEST", confirmation=CONFIRMATION_TOKEN,
                )
            self.assertTrue(result.pre_guard.valid)
            self.assertTrue(result.post_guard.valid)
            self.assertEqual(len(result.allowed_changed_paths), 3)

    def test_safe_rollback_removes_only_exact_isolated_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            card = _card(root)
            guard = root / "guard.json"
            create_saroo_card_inventory(card, guard)
            deployment = _deployment(card)
            with (
                patch.object(pre_mod, "ACCEPTED_R25_BIN_SHA256", sha256(_BIN).hexdigest()),
                patch.object(pre_mod, "ACCEPTED_R25_CUE_SHA256", sha256(_CUE).hexdigest()),
            ):
                status = _safe_rollback_new_directory(card, deployment, guard)
            self.assertEqual(status, "verified rollback succeeded; original whole-card baseline restored")
            self.assertFalse(deployment.plan.destination_directory.exists())


if __name__ == "__main__":
    unittest.main()
