"""SDDRV210 R6: interactive velocity sweep over the audited R5 level-seed path.

R6 changes no SDDRV command semantics, tone-bank bytes, mapping, or SCSP access.
It preserves R5 and records that the current diagnostic UI can move Note-On
velocity across 1..127 in steps of 8 using B/C, with default velocity 100.
"""

from __future__ import annotations

from . import sbl_midi_calibration_sddrv210_voice_probe_level_seed as _r5

SaturnSblMidiCalibrationCandidateError = _r5.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _r5.SaturnSblMidiCalibrationCandidateResult

VELOCITY_SWEEP_REVISION = "R6_INTERACTIVE_VELOCITY"
VELOCITY_MIN = 1
VELOCITY_MAX = 127
VELOCITY_STEP = 8
VELOCITY_DEFAULT = 100


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_interactive_velocity_probe"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "voice_probe_velocity_sweep": VELOCITY_SWEEP_REVISION,
            "velocity_default": VELOCITY_DEFAULT,
            "velocity_min": VELOCITY_MIN,
            "velocity_max": VELOCITY_MAX,
            "velocity_step": VELOCITY_STEP,
            "velocity_decrease_button": "B",
            "velocity_increase_button": "C",
            "velocity_change_forces_note_off": True,
            "r5_level_seed_preserved": True,
            "tone_banks_unchanged": True,
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    old_manifest = _r5._telemetry_manifest

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _r5._telemetry_manifest = telemetry_manifest
    try:
        return _r5.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
    finally:
        _r5._telemetry_manifest = old_manifest
