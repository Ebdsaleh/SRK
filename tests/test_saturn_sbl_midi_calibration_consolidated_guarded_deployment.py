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
    EXPECTED_CUE_SHA256,
    EXPECTED_FAMILY_COUNT,
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
        manifest_sha256="1" * 64,
        build_report_sha256="2" * 64,
        area_map_sha256=EXPECTED_AREA_MAP_SHA256,
        bin_sha256=EXPECTED_BIN_SHA256,
        cue_sha256=EXPECTED_CUE_SHA256,
        program_count=EXPECTED_PROGRAM_COUNT,
        family_count=EXPECTED_FAMILY_COUNT,
        largest_family_bytes=EXPECTED_MAX_FAMILY_BYTES,
        screen_owned_sbl_lifecycle=True,
        raw_scsp_audio_test_retained=True,
        driver_execution_telemetry=True,
        sega_oneshot_order=True,
        deployable_verified_against_iso=True,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_consolidated_guard_locks_exact_accepted_oneshot_pre_media_evidence() -> None:
    assert EXPECTED_AREA_MAP_SHA256 == (
        "40530e1a0f1b147a6f87aaaa00de7593b82fbec806f291bcddc2b09d865a4605"
    )
    assert EXPECTED_BIN_SHA256 == (
        "56fc685e8df1e3f4f28806ef703bbfcc26b5bd48105a7aeae5917f7158f967ca"
    )
    assert EXPECTED_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )
    _validate_pre_media(_accepted_report())


def test_consolidated_guard_refuses_lifecycle_telemetry_or_oneshot_regression() -> None:
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
    with pytest.raises(
        SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
        match="one-shot",
    ):
        _validate_pre_media(_accepted_report(sega_oneshot_order=False))


def test_consolidated_guard_has_fixed_isolated_oneshot_destination_and_token() -> None:
    assert CATEGORY == "TEST"
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT"


def test_allowed_paths_are_only_new_oneshot_directory_and_bin_cue() -> None:
    destination = Path(
        "D:/saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT"
    )
    deployment = SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=destination / "SRK-Diagnostics.bin",
        destination_cue=destination / "SRK-Diagnostics.cue",
    )
    assert set(_allowed_paths(deployment)) == {
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT/SRK-Diagnostics.bin",
        "saroo/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT/SRK-Diagnostics.cue",
    }


def test_apply_rejects_wrong_confirmation_before_audit_or_card_access() -> None:
    with patch(
        "rikai_kotoba.hardware.saturn."
        "sbl_midi_calibration_consolidated_guarded_deployment._audit"
    ) as audit:
        with pytest.raises(
            SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
            match="DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT",
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
        manifest = card / "oneshot-card-before.json"
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
