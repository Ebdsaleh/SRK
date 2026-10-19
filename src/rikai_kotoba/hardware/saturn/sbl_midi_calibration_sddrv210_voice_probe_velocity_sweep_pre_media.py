"""Read-only pre-media audit for R6 interactive MIDI velocity sweep."""

from __future__ import annotations

from pathlib import Path

from . import sbl_midi_calibration_sddrv210_voice_probe_level_seed_pre_media as _r5
from .sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep import (
    VELOCITY_DEFAULT,
    VELOCITY_MAX,
    VELOCITY_MIN,
    VELOCITY_STEP,
    VELOCITY_SWEEP_REVISION,
)

SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError = (
    _r5.SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError
)


def audit_sddrv210_velocity_sweep_pre_media(project_directory):
    report = _r5.audit_sddrv210_level_seed_pre_media(project_directory)
    root = Path(project_directory).expanduser().resolve(strict=True)
    base = _r5._r4._r3._sddrv._base

    manifest_path = base._file(root, base._MANIFEST, "R6 velocity-sweep manifest")
    manifest = base._load_json(manifest_path, "R6 velocity-sweep manifest")
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_interactive_velocity_probe") is not True:
        raise SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError(
            "R6 interactive-velocity manifest policy is missing"
        )
    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError(
            "R6 velocity-sweep telemetry record is missing"
        )
    expected = {
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
    for key,wanted in expected.items():
        base._expect(telemetry.get(key), wanted, f"R6 velocity telemetry {key}")

    header=(root/"src"/"srk_diag_midi_test.h").read_text(encoding="utf-8")
    midi=(root/"src"/"srk_diag_midi_test.c").read_text(encoding="utf-8")
    app=(root/"src"/"srk_diag_app.c").read_text(encoding="utf-8")

    for required in (
        "#define SRK_DIAG_MIDI_DEFAULT_VELOCITY 100u",
        "#define SRK_DIAG_MIDI_VELOCITY_STEP 8u",
        "srk_diag_midi_test_move_velocity",
    ):
        if required not in header:
            raise SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError(
                f"R6 generated MIDI header lost required anchor: {required}"
            )
    for required in (
        "if(value < 1)",
        "if(value > 127)",
        "state->velocity = (srk_u8)value;",
    ):
        if required not in midi:
            raise SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError(
                f"R6 generated MIDI source lost required anchor: {required}"
            )
    for required in (
        '"B/C Velocity -/+ (1..127)"',
        "SRK_DIAG_BUTTON_B",
        "SRK_DIAG_BUTTON_C",
        "srk_diag_midi_note_off(app, host);",
        "SRK_DIAG_MIDI_VELOCITY_STEP",
    ):
        if required not in app:
            raise SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError(
                f"R6 generated diagnostic app lost required anchor: {required}"
            )
    return report
