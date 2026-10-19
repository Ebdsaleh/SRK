from __future__ import annotations

from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep import (
    VELOCITY_DEFAULT,
    VELOCITY_MAX,
    VELOCITY_MIN,
    VELOCITY_STEP,
    VELOCITY_SWEEP_REVISION,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationSddrv210VelocitySweepGuardedDeploymentError,
    _require_final_hash_lock,
)

ROOT=Path(__file__).resolve().parents[1]
DIAG=ROOT/"integrations"/"saturn"/"diagnostics"


def test_r6_velocity_contract_is_exact():
    assert VELOCITY_SWEEP_REVISION=="R6_INTERACTIVE_VELOCITY"
    assert VELOCITY_DEFAULT==100
    assert VELOCITY_MIN==1
    assert VELOCITY_MAX==127
    assert VELOCITY_STEP==8


def test_r6_diagnostic_controls_velocity_and_forces_note_off():
    header=(DIAG/"srk_diag_midi_test.h").read_text(encoding="utf-8")
    midi=(DIAG/"srk_diag_midi_test.c").read_text(encoding="utf-8")
    app=(DIAG/"srk_diag_app.c").read_text(encoding="utf-8")
    assert "#define SRK_DIAG_MIDI_VELOCITY_STEP 8u" in header
    assert "void srk_diag_midi_test_move_velocity" in midi
    assert "if(value < 1)" in midi and "if(value > 127)" in midi
    assert '"B/C Velocity -/+ (1..127)"' in app
    velocity_block=app.index("SRK_DIAG_BUTTON_B) ||")
    note_off=app.index("srk_diag_midi_note_off(app, host);",velocity_block)
    move=app.index("srk_diag_midi_test_move_velocity(",velocity_block)
    assert velocity_block < note_off < move


def test_r6_manifest_preserves_r5_and_bank_mapping():
    document=_telemetry_manifest({"policy":{},"sbl_midi_calibration":{"telemetry":{}}})
    assert document["policy"]["sddrv210_interactive_velocity_probe"] is True
    telemetry=document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["voice_probe_velocity_sweep"]==VELOCITY_SWEEP_REVISION
    assert telemetry["velocity_default"]==100
    assert telemetry["velocity_min"]==1
    assert telemetry["velocity_max"]==127
    assert telemetry["velocity_step"]==8
    assert telemetry["velocity_decrease_button"]=="B"
    assert telemetry["velocity_increase_button"]=="C"
    assert telemetry["velocity_change_forces_note_off"] is True
    assert telemetry["r5_level_seed_preserved"] is True
    assert telemetry["tone_banks_unchanged"] is True


def test_current_candidate_routes_r6_over_r5():
    source_root=ROOT/"src"/"rikai_kotoba"/"hardware"/"saturn"
    contract=(source_root/"sbl_midi_calibration_candidate_contract.py").read_text(encoding="utf-8")
    r6=(source_root/"sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep.py").read_text(encoding="utf-8")
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep "
        "as _sddrv210_probe" in contract
    )
    assert "sbl_midi_calibration_sddrv210_voice_probe_level_seed as _r5" in r6


def test_r6_guard_is_separate_and_fails_closed_before_hash_lock():
    assert DESTINATION_NAME=="SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VELOCITY-SWEEP-R6"
    assert CONFIRMATION_TOKEN=="DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VELOCITY-SWEEP-R6"
    assert EXPECTED_MANIFEST_SHA256 is None
    assert EXPECTED_BUILD_REPORT_SHA256 is None
    assert EXPECTED_BIN_SHA256 is None
    assert EXPECTED_CUE_SHA256 is None
    with pytest.raises(
        SaturnSblMidiCalibrationSddrv210VelocitySweepGuardedDeploymentError,
        match="intentionally blocked",
    ):
        _require_final_hash_lock()
