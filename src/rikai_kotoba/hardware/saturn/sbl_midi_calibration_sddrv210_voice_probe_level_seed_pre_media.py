"""Read-only pre-media audit for the SDDRV210 R5 Direct-MIDI level seed."""

from __future__ import annotations

from pathlib import Path

from . import sbl_midi_calibration_sddrv210_voice_probe_keyed_pre_media as _r4
from .sbl_midi_calibration_sddrv210_voice_probe_level_seed import (
    CHANNEL_VOLUME_CONTROLLER,
    EXPRESSION_CONTROLLER,
    LEVEL_SEED_REVISION,
    LEVEL_SEED_VALUE,
)


SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError = (
    _r4.SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedPreMediaError
)


def audit_sddrv210_level_seed_pre_media(project_directory):
    report = _r4.audit_sddrv210_voice_probe_keyed_pre_media(project_directory)

    root = Path(project_directory).expanduser().resolve(strict=True)
    base = _r4._r3._sddrv._base
    manifest_path = base._file(
        root, base._MANIFEST, "SDDRV210 R5 level-seed manifest"
    )
    manifest = base._load_json(manifest_path, "SDDRV210 R5 level-seed manifest")

    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_direct_midi_level_seed") is not True:
        raise SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError(
            "R5 Direct-MIDI level-seed manifest policy is missing"
        )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError(
            "R5 Direct-MIDI level-seed telemetry record is missing"
        )

    expected = {
        "voice_probe_level_seed": LEVEL_SEED_REVISION,
        "channel_volume_controller": CHANNEL_VOLUME_CONTROLLER,
        "channel_volume_value": LEVEL_SEED_VALUE,
        "expression_controller": EXPRESSION_CONTROLLER,
        "expression_value": LEVEL_SEED_VALUE,
        "level_seed_before_bank_program": True,
        "level_seed_every_program_selection": True,
        "level_seed_preserves_keyed_probe": True,
        "level_seed_scsp_direct_writes": False,
        "level_seed_dummy_sequence": False,
        "r4_physical_keyed_tl": "0x00FF",
        "r4_physical_keyed_mixer": "0xE000",
        "r4_authored_program16_tl": "0x19",
    }
    for key, wanted in expected.items():
        base._expect(telemetry.get(key), wanted, f"R5 level-seed telemetry {key}")

    runtime = base._file(
        root, base._RUNTIME, "SDDRV210 R5 level-seed runtime"
    ).read_text(encoding="utf-8", errors="strict")
    base._require_source_anchors(
        runtime,
        (
            "#define SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER 7u",
            "#define SRK_SBL_CAL_EXPRESSION_CONTROLLER 11u",
            "#define SRK_SBL_CAL_LEVEL_SEED_VALUE 127u",
            "#define SRK_SBL_CAL_ERR_LEVEL_SEED 12u",
            "SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE",
            "SRK_SBL_CAL_EXPRESSION_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE",
            "SRK_SBL_CAL_BANK_CONTROLLER,0u",
            "SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u",
            "latched_keyed_scsp_total_level",
            "latched_keyed_scsp_mixer",
        ),
        "SDDRV210 R5 level-seed runtime",
    )

    start = runtime.find("static int srk_cal_select_program(void *context,unsigned int program){")
    end = runtime.find("static int srk_cal_set_pan(", start)
    if start < 0 or end < 0:
        raise SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError(
            "R5 program-selection function boundary changed"
        )
    select = runtime[start:end]
    order = (
        select.find("SND_MoveData((Uint16 *)srk_cal_family"),
        select.find("SND_ChgMix(0,0)"),
        select.find("SND_SetTlVl("),
        select.find("SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE"),
        select.find("SRK_SBL_CAL_EXPRESSION_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE"),
        select.find("SRK_SBL_CAL_BANK_CONTROLLER,0u"),
        select.find("SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u"),
    )
    if any(index < 0 for index in order) or tuple(sorted(order)) != order:
        raise SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError(
            "R5 Direct-MIDI ordering is not MoveData < ChgMix < SetTlVl < "
            "CC7 < CC11 < CC32 < Program Change"
        )
    if "SND_StartSeq" in runtime:
        raise SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError(
            "R5 Direct-MIDI runtime unexpectedly contains SND_StartSeq"
        )

    return report
