"""Guarded deployment for the SDDRV210 voice-allocation probe candidate."""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_consolidated_guarded_deployment as _guard
from .sbl_midi_calibration_sddrv210 import SDDRV210_SHA256
from .sbl_midi_calibration_sddrv210_voice_probe_pre_media import (
    audit_sddrv210_voice_probe_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VOICE-PROBE"
DESTINATION_NAME = "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VOICE-PROBE"
CATEGORY = "TEST"
EXPECTED_SOUND_DRIVER_SHA256 = SDDRV210_SHA256

# Deliberately unset until the first off-card voice-probe build is audited.
EXPECTED_MANIFEST_SHA256: str | None = None
EXPECTED_BUILD_REPORT_SHA256: str | None = None
EXPECTED_BIN_SHA256: str | None = None
EXPECTED_CUE_SHA256: str | None = None

SaturnSblMidiCalibrationSddrv210VoiceProbeGuardedDeploymentError = (
    _guard.SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError
)


def _require_final_hash_lock() -> tuple[str, str, str, str]:
    values = (
        EXPECTED_MANIFEST_SHA256,
        EXPECTED_BUILD_REPORT_SHA256,
        EXPECTED_BIN_SHA256,
        EXPECTED_CUE_SHA256,
    )
    if all(isinstance(value, str) and len(value) == 64 for value in values):
        return values  # type: ignore[return-value]
    raise SaturnSblMidiCalibrationSddrv210VoiceProbeGuardedDeploymentError(
        "SDDRV210 voice-probe deployment is intentionally blocked until its "
        "manifest, build-report, BIN and CUE hashes are audited and hard locked"
    )


def audit_sddrv210_voice_probe_guarded_candidate(project_directory):
    report = audit_sddrv210_voice_probe_pre_media(project_directory)
    if report.sound_driver_sha256.lower() != EXPECTED_SOUND_DRIVER_SHA256:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeGuardedDeploymentError(
            "SDDRV210 voice-probe escaped the exact sound-driver hash lock"
        )
    return report


@contextmanager
def _contract():
    manifest_sha, report_sha, bin_sha, cue_sha = _require_final_hash_lock()
    saved = {
        "CONFIRMATION_TOKEN": _guard.CONFIRMATION_TOKEN,
        "DESTINATION_NAME": _guard.DESTINATION_NAME,
        "EXPECTED_MANIFEST_SHA256": _guard.EXPECTED_MANIFEST_SHA256,
        "EXPECTED_BUILD_REPORT_SHA256": _guard.EXPECTED_BUILD_REPORT_SHA256,
        "EXPECTED_BIN_SHA256": _guard.EXPECTED_BIN_SHA256,
        "EXPECTED_CUE_SHA256": _guard.EXPECTED_CUE_SHA256,
        "audit": _guard.audit_consolidated_midi_calibration_pre_media,
    }
    _guard.CONFIRMATION_TOKEN = CONFIRMATION_TOKEN
    _guard.DESTINATION_NAME = DESTINATION_NAME
    _guard.EXPECTED_MANIFEST_SHA256 = manifest_sha
    _guard.EXPECTED_BUILD_REPORT_SHA256 = report_sha
    _guard.EXPECTED_BIN_SHA256 = bin_sha
    _guard.EXPECTED_CUE_SHA256 = cue_sha
    _guard.audit_consolidated_midi_calibration_pre_media = (
        audit_sddrv210_voice_probe_guarded_candidate
    )
    try:
        yield
    finally:
        _guard.CONFIRMATION_TOKEN = saved["CONFIRMATION_TOKEN"]
        _guard.DESTINATION_NAME = saved["DESTINATION_NAME"]
        _guard.EXPECTED_MANIFEST_SHA256 = saved["EXPECTED_MANIFEST_SHA256"]
        _guard.EXPECTED_BUILD_REPORT_SHA256 = saved["EXPECTED_BUILD_REPORT_SHA256"]
        _guard.EXPECTED_BIN_SHA256 = saved["EXPECTED_BIN_SHA256"]
        _guard.EXPECTED_CUE_SHA256 = saved["EXPECTED_CUE_SHA256"]
        _guard.audit_consolidated_midi_calibration_pre_media = saved["audit"]


def prepare_sddrv210_voice_probe_guarded_deployment(project_directory, card_root, guard_manifest):
    with _contract():
        return _guard.prepare_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory, card_root, guard_manifest
        )


def apply_sddrv210_voice_probe_guarded_deployment(
    project_directory,
    card_root,
    guard_manifest,
    *,
    expected_guard_manifest_sha256: str,
    confirmation: str,
):
    with _contract():
        return _guard.apply_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory,
            card_root,
            guard_manifest,
            expected_guard_manifest_sha256=expected_guard_manifest_sha256,
            confirmation=confirmation,
        )
