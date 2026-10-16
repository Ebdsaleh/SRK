from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

import pytest

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_guarded_deployment import (
    CATEGORY,
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationGate4GuardedDeploymentError,
    _allowed_paths,
    apply_sbl_midi_calibration_gate4_guarded_deployment,
    prepare_sbl_midi_calibration_gate4_guarded_deployment,
)


def test_gate4_guard_locks_exact_accepted_pre_media_evidence() -> None:
    assert EXPECTED_MANIFEST_SHA256 == (
        "5aecb9b4d660fa6618f3a60217a762a200c1f5be74a2d30af8109707ef4fd8ba"
    )
    assert EXPECTED_BUILD_REPORT_SHA256 == (
        "b63b64b4b74dcc64af376084ba1eaf2fa947497718e7234bf244051951864df5"
    )
    assert EXPECTED_AREA_MAP_SHA256 == (
        "b4a249b0d9df4985ad6f3357cd978e017b41bbf82d0d6603f378d968c6b67001"
    )
    assert EXPECTED_BIN_SHA256 == (
        "78af4a56160f5ce1ff4778b313ad233a5014c7cbd274cb4d25515b22f87947d0"
    )
    assert EXPECTED_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )


def test_gate4_guard_has_fixed_isolated_destination_and_token() -> None:
    assert CATEGORY == "TEST"
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-GATE4"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-GATE4"


def test_allowed_paths_are_only_new_gate4_directory_and_bin_cue() -> None:
    destination = Path("D:/saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE4")
    deployment = SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=destination / "SRK-Diagnostics.bin",
        destination_cue=destination / "SRK-Diagnostics.cue",
    )
    assert set(_allowed_paths(deployment)) == {
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE4",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE4/SRK-Diagnostics.bin",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE4/SRK-Diagnostics.cue",
    }


def test_apply_rejects_wrong_confirmation_before_audit_or_card_access() -> None:
    with patch(
        "rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_guarded_deployment._audit"
    ) as audit:
        with pytest.raises(
            SaturnSblMidiCalibrationGate4GuardedDeploymentError,
            match="DEPLOY-SBL-MIDI-CALIBRATION-GATE4",
        ):
            apply_sbl_midi_calibration_gate4_guarded_deployment(
                "missing-project",
                "missing-card",
                "missing-guard.json",
                expected_guard_manifest_sha256="0" * 64,
                confirmation="WRONG",
            )
    audit.assert_not_called()


def test_prepare_rejects_guard_manifest_stored_on_card_before_audit() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        card = Path(temp_dir) / "CARD"
        card.mkdir()
        manifest = card / "gate4-card-before.json"
        with patch(
            "rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_guarded_deployment._audit"
        ) as audit:
            with pytest.raises(
                SaturnSblMidiCalibrationGate4GuardedDeploymentError,
                match="outside",
            ):
                prepare_sbl_midi_calibration_gate4_guarded_deployment(
                    "missing-project",
                    card,
                    manifest,
                )
        audit.assert_not_called()


def test_guard_source_exposes_no_format_or_whole_card_delete_path() -> None:
    source = Path(__file__).resolve().parents[1] / (
        "src/rikai_kotoba/hardware/saturn/"
        "sbl_midi_calibration_gate4_guarded_deployment.py"
    )
    text = source.read_text(encoding="utf-8")

    for forbidden in (
        "format(",
        "diskpart",
        "mkfs",
        "rmtree(card",
        "rmtree(card_root",
        "shutil.rmtree",
    ):
        assert forbidden not in text

    assert "destination_name=DESTINATION_NAME" in text
    assert "category=CATEGORY" in text
    assert "allowed_changed_paths=allowed" in text
