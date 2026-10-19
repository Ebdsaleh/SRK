"""Fail-closed guarded deployment for R6 interactive velocity sweep."""

from __future__ import annotations
from contextlib import contextmanager

from . import sbl_midi_calibration_consolidated_guarded_deployment as _guard
from .sbl_midi_calibration_sddrv210 import SDDRV210_SHA256
from .sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep_pre_media import (
    FINAL_BUILD_REPORT_SHA256,
    FINAL_DEPLOYABLE_BIN_SHA256,
    FINAL_DEPLOYABLE_CUE_SHA256,
    FINAL_MANIFEST_SHA256,
    audit_sddrv210_velocity_sweep_pre_media,
)

CONFIRMATION_TOKEN="DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VELOCITY-SWEEP-R6"
DESTINATION_NAME="SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VELOCITY-SWEEP-R6"
EXPECTED_SOUND_DRIVER_SHA256=SDDRV210_SHA256

EXPECTED_MANIFEST_SHA256: str | None=FINAL_MANIFEST_SHA256
EXPECTED_BUILD_REPORT_SHA256: str | None=FINAL_BUILD_REPORT_SHA256
EXPECTED_BIN_SHA256: str | None=FINAL_DEPLOYABLE_BIN_SHA256
EXPECTED_CUE_SHA256: str | None=FINAL_DEPLOYABLE_CUE_SHA256

SaturnSblMidiCalibrationSddrv210VelocitySweepGuardedDeploymentError=(
    _guard.SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError
)

def _require_final_hash_lock():
    values=(EXPECTED_MANIFEST_SHA256,EXPECTED_BUILD_REPORT_SHA256,EXPECTED_BIN_SHA256,EXPECTED_CUE_SHA256)
    if all(isinstance(v,str) and len(v)==64 for v in values):
        return values
    raise SaturnSblMidiCalibrationSddrv210VelocitySweepGuardedDeploymentError(
        "SDDRV210 R6 velocity-sweep deployment is intentionally blocked until "
        "manifest, build-report, BIN and CUE hashes are audited and hard locked"
    )

def audit_sddrv210_velocity_sweep_guarded_candidate(project_directory):
    report=audit_sddrv210_velocity_sweep_pre_media(project_directory)
    if report.sound_driver_sha256.lower()!=EXPECTED_SOUND_DRIVER_SHA256:
        raise SaturnSblMidiCalibrationSddrv210VelocitySweepGuardedDeploymentError(
            "R6 velocity sweep escaped exact SDDRV210 hash lock"
        )
    return report

@contextmanager
def _contract():
    manifest_sha,report_sha,bin_sha,cue_sha=_require_final_hash_lock()
    saved=(
        _guard.CONFIRMATION_TOKEN,_guard.DESTINATION_NAME,
        _guard.EXPECTED_MANIFEST_SHA256,_guard.EXPECTED_BUILD_REPORT_SHA256,
        _guard.EXPECTED_BIN_SHA256,_guard.EXPECTED_CUE_SHA256,
        _guard.audit_consolidated_midi_calibration_pre_media,
    )
    _guard.CONFIRMATION_TOKEN=CONFIRMATION_TOKEN
    _guard.DESTINATION_NAME=DESTINATION_NAME
    _guard.EXPECTED_MANIFEST_SHA256=manifest_sha
    _guard.EXPECTED_BUILD_REPORT_SHA256=report_sha
    _guard.EXPECTED_BIN_SHA256=bin_sha
    _guard.EXPECTED_CUE_SHA256=cue_sha
    _guard.audit_consolidated_midi_calibration_pre_media=audit_sddrv210_velocity_sweep_guarded_candidate
    try:
        yield
    finally:
        (
            _guard.CONFIRMATION_TOKEN,_guard.DESTINATION_NAME,
            _guard.EXPECTED_MANIFEST_SHA256,_guard.EXPECTED_BUILD_REPORT_SHA256,
            _guard.EXPECTED_BIN_SHA256,_guard.EXPECTED_CUE_SHA256,
            _guard.audit_consolidated_midi_calibration_pre_media,
        )=saved

def prepare_sddrv210_velocity_sweep_guarded_deployment(project_directory,card_root,guard_manifest):
    with _contract():
        return _guard.prepare_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory,card_root,guard_manifest
        )

def apply_sddrv210_velocity_sweep_guarded_deployment(
    project_directory,card_root,guard_manifest,*,expected_guard_manifest_sha256,confirmation
):
    with _contract():
        return _guard.apply_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory,card_root,guard_manifest,
            expected_guard_manifest_sha256=expected_guard_manifest_sha256,
            confirmation=confirmation,
        )
