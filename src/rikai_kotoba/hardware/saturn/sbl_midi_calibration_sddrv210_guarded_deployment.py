"""Guarded SAROO deployment contract for the SDDRV Ver 2.10 one-shot.

The supplied 2026-10-17 build proves the exact Ver 2.10 input transition. The
fresh telemetry-correct 2026-10-18 build is now hard-locked by exact manifest,
build-report, BIN and CUE SHA-256 values. The established whole-card
guard/deployment implementation is reused under an SDDRV210-specific destination
and confirmation token; PREPARE remains read-only with respect to deployment and
APPLY still requires the reviewed whole-card guard hash plus explicit confirmation.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_consolidated_guarded_deployment as _guard
from .sbl_midi_calibration_sddrv210 import SDDRV210_SHA256
from .sbl_midi_calibration_sddrv210_pre_media import (
    TRANSITION_BUILD_REPORT_SHA256,
    TRANSITION_DEPLOYABLE_BIN_SHA256,
    TRANSITION_DEPLOYABLE_CUE_SHA256,
    TRANSITION_MANIFEST_SHA256,
    audit_sddrv210_midi_calibration_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT-SDDRV210"
DESTINATION_NAME = "SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT-SDDRV210"
CATEGORY = "TEST"
EXPECTED_SOUND_DRIVER_SHA256 = SDDRV210_SHA256

# Exact telemetry-correct SDDRV210 build audited off-card on Eridu on
# 2026-10-18. These hashes are the deployment allow-list, never wildcards.
EXPECTED_MANIFEST_SHA256: str | None = "799197d9babc8ce2a3e14cae5a32f84dd89369fc50b12a5ad8e9d23e284f1d82"
EXPECTED_BUILD_REPORT_SHA256: str | None = "cb91a8a35b2c5744c042b4b6abe4284e27fca31fda3aa7bbdd9991e2d4e14417"
EXPECTED_BIN_SHA256: str | None = "b43ac550f5560d1a99e686833e826e38167b28bdbc8e4dd49b7c270754c3189c"
EXPECTED_CUE_SHA256: str | None = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"

SaturnSblMidiCalibrationSddrv210GuardedDeploymentError = (
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
    raise SaturnSblMidiCalibrationSddrv210GuardedDeploymentError(
        "SDDRV210 deployment is intentionally blocked: rebuild the telemetry-correct "
        "candidate after pulling this commit, then hard-lock its manifest, build-report, "
        "BIN and CUE SHA-256 values before any SAROO write"
    )


def audit_sddrv210_guarded_candidate(project_directory):
    """Run the read-only SDDRV210 audit; never touches the SAROO card."""

    report = audit_sddrv210_midi_calibration_pre_media(project_directory)
    if report.sound_driver_sha256.lower() != EXPECTED_SOUND_DRIVER_SHA256:
        raise SaturnSblMidiCalibrationSddrv210GuardedDeploymentError(
            "SDDRV210 sound-driver hash escaped the guarded contract"
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
    _guard.audit_consolidated_midi_calibration_pre_media = audit_sddrv210_guarded_candidate
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


def prepare_sddrv210_guarded_deployment(project_directory, card_root, guard_manifest):
    """Prepare only after the exact telemetry-correct artifact hashes are locked."""

    with _contract():
        return _guard.prepare_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory,
            card_root,
            guard_manifest,
        )


def apply_sddrv210_guarded_deployment(
    project_directory,
    card_root,
    guard_manifest,
    *,
    expected_guard_manifest_sha256: str,
    confirmation: str,
):
    """Apply only after both final artifact lock and whole-card guard approval."""

    with _contract():
        return _guard.apply_sbl_midi_calibration_consolidated_guarded_deployment(
            project_directory,
            card_root,
            guard_manifest,
            expected_guard_manifest_sha256=expected_guard_manifest_sha256,
            confirmation=confirmation,
        )
