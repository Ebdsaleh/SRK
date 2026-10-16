from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

import pytest

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_consolidated_guarded_deployment import (
    CATEGORY,
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_FAMILY_COUNT,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_MAX_FAMILY_BYTES,
    EXPECTED_PROGRAM_COUNT,
    SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
    _allowed_paths,
    _validate_pre_media,
    apply_sbl_midi_calibration_consolidated_guarded_deployment,
    prepare_sbl_midi_calibration_consolidated_guarded_deployment,
)


def _accepted_report(**changes):
    values = dict(
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
        build_report_sha256=EXPECTED_BUILD_REPORT_SHA256,
        area_map_sha256=EXPECTED_AREA_MAP_SHA256,
        bin_sha256=EXPECTED_BIN_SHA256,
        cue_sha256=EXPECTED_CUE_SHA256,
        program_count=EXPECTED_PROGRAM_COUNT,
        family_count=EXPECTED_FAMILY_COUNT,
        largest_family_bytes=EXPECTED_MAX_FAMILY_BYTES,
        screen_owned_sbl_lifecycle=True,
        raw_scsp_audio_test_retained=True,
        driver_execution_telemetry=True,
        deployable_verified_against_iso=True,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_consolidated_guard_locks_exact_accepted_pre_media_evidence() -> None:
    assert EXPECTED_MANIFEST_SHA256 == (
        "5493e9e5b8665f372a8474e4c95ff29b043502d2dd8b970f72f260c99ac9eaf2"
    )
    assert EXPECTED_BUILD_REPORT_SHA256 == (
        "c8586839b651da3572ddffe284cc54f2f9fba054a2a83ae59db0df5fe0bb8955"
    )
    assert EXPECTED_AREA_MAP_SHA256 == (
        "40530e1a0f1b147a6f87aaaa00de7593b82fbec806f291bcddc2b09d865a4605"
    )
    assert EXPECTED_BIN_SHA256 == (
        "3c03f4c49dd70e7f142faaa3b1fc69b1e1735eb13b5524beed0b46a4d3bfaff6"
    )
    assert EXPECTED_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )
    _validate_pre_media(_accepted_report())


def test_consolidated_guard_refuses_lifecycle_or_telemetry_regression() -> None:
    with pytest.raises(
        SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
        match="screen-owned",
    ):
        _validate_pre_media(_accepted_report(screen_owned_sbl_lifecycle=False))
    with pytest.raises(
        SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
        match="telemetry",
    ):
        _validate_pre_media(_accepted_report(driver_execution_telemetry=False))


def test_consolidated_guard_has_fixed_isolated_destination_and_token() -> None:
    assert CATEGORY == "TEST"
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-CONSOLIDATED"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-CONSOLIDATED"


def test_allowed_paths_are_only_new_consolidated_directory_and_bin_cue() -> None:
    destination = Path(
        "D:/saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-CONSOLIDATED"
    )
    deployment = SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=destination / "SRK-Diagnostics.bin",
        destination_cue=destination / "SRK-Diagnostics.cue",
    )
    assert set(_allowed_paths(deployment)) == {
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-CONSOLIDATED",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-CONSOLIDATED/SRK-Diagnostics.bin",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-CONSOLIDATED/SRK-Diagnostics.cue",
    }


def test_apply_rejects_wrong_confirmation_before_audit_or_card_access() -> None:
    with patch(
        "rikai_kotoba.hardware.saturn."
        "sbl_midi_calibration_consolidated_guarded_deployment._audit"
    ) as audit:
        with pytest.raises(
            SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
            match="DEPLOY-SBL-MIDI-CALIBRATION-CONSOLIDATED",
        ):
            apply_sbl_midi_calibration_consolidated_guarded_deployment(
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
        manifest = card / "consolidated-card-before.json"
        with patch(
            "rikai_kotoba.hardware.saturn."
            "sbl_midi_calibration_consolidated_guarded_deployment._audit"
        ) as audit:
            with pytest.raises(
                SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
                match="outside",
            ):
                prepare_sbl_midi_calibration_consolidated_guarded_deployment(
                    "missing-project",
                    card,
                    manifest,
                )
        audit.assert_not_called()


def test_guard_source_exposes_no_format_or_whole_card_delete_path() -> None:
    source = Path(__file__).resolve().parents[1] / (
        "src/rikai_kotoba/hardware/saturn/"
        "sbl_midi_calibration_consolidated_guarded_deployment.py"
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
