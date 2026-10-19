"""Read-only pre-media audit for the SDDRV210 R4 keyed-state probe."""

from __future__ import annotations

from pathlib import Path

from . import sbl_midi_calibration_sddrv210_voice_probe_redteam_pre_media as _r3
from .sbl_midi_calibration_sddrv210_voice_probe_keyed import KEYED_SNAPSHOT_REVISION


SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedPreMediaError = (
    _r3.SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError
)


_RUNTIME_HEADER = "src/srk_saturn_sbl_midi_calibration_runtime.h"

FINAL_MANIFEST_SHA256 = "0c0c6d2d83e2b12b7e841f06641c1fe8798168ef056f46bf527df6683a75a71d"
FINAL_BUILD_REPORT_SHA256 = "ec98c3cd50641682fd37408ba74608cbf6749a81f918d93f7853b834a9a9c232"
FINAL_DEPLOYABLE_BIN_SHA256 = "7101e91c555e8bab28f6fd6b3b7cf73906738cf503919c8647e8986c3d5cd7b7"
FINAL_DEPLOYABLE_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"


def final_hash_lock_matches(report) -> bool:
    return (
        report.manifest_sha256.lower() == FINAL_MANIFEST_SHA256
        and report.build_report_sha256.lower() == FINAL_BUILD_REPORT_SHA256
        and report.bin_sha256.lower() == FINAL_DEPLOYABLE_BIN_SHA256
        and report.cue_sha256.lower() == FINAL_DEPLOYABLE_CUE_SHA256
    )


def audit_sddrv210_voice_probe_keyed_pre_media(project_directory):
    report = _r3.audit_sddrv210_voice_probe_redteam_pre_media(project_directory)

    root = Path(project_directory).expanduser().resolve(strict=True)
    manifest_path = _r3._sddrv._base._file(
        root, _r3._sddrv._base._MANIFEST, "SDDRV210 R4 keyed probe manifest"
    )
    manifest = _r3._sddrv._base._load_json(
        manifest_path, "SDDRV210 R4 keyed probe manifest"
    )

    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_voice_probe_keyed_snapshot") is not True:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedPreMediaError(
            "R4 keyed-snapshot manifest policy is missing"
        )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedPreMediaError(
            "R4 keyed-snapshot telemetry manifest record is missing"
        )

    expected = {
        "voice_probe_keyed_snapshot": KEYED_SNAPSHOT_REVISION,
        "keyed_snapshot_requires_kyonb": True,
        "keyed_snapshot_refreshes_while_held": True,
        "keyed_snapshot_persists_after_note_off": True,
        "keyed_snapshot_is_read_only": True,
        "raw_scsp_reference_stopped_control": "0x0020",
        "raw_scsp_reference_stopped_mixer": "0x0000",
        "raw_scsp_reference_audible_control": "0x0820",
        "raw_scsp_reference_audible_mixer_volume4_center": "0x8000",
    }
    for key, wanted in expected.items():
        _r3._sddrv._base._expect(
            telemetry.get(key), wanted, f"R4 keyed telemetry {key}"
        )

    runtime_header = _r3._sddrv._base._file(
        root, _RUNTIME_HEADER, "SDDRV210 R4 keyed probe runtime header"
    ).read_text(encoding="utf-8", errors="strict")
    _r3._sddrv._base._require_source_anchors(
        runtime_header,
        (
            "unsigned int keyed_scsp_slot;",
            "unsigned int latched_keyed_scsp_slot;",
        ),
        "SDDRV210 R4 keyed runtime header",
    )

    runtime = _r3._sddrv._base._file(
        root, _r3._sddrv._base._RUNTIME, "SDDRV210 R4 keyed probe runtime"
    ).read_text(encoding="utf-8", errors="strict")
    _r3._sddrv._base._require_source_anchors(
        runtime,
        (
            "s->keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE",
            "s->latched_keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE",
            "if((srk_cal_probe_reg16(r+0x00UL)&SRK_SBL_CAL_SCSP_KYONB_MASK)!=0u)",
            "s->latched_keyed_scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL)",
            "s->latched_keyed_scsp_total_level=(unsigned int)srk_cal_probe_reg16(r+0x0CUL)",
            "s->latched_keyed_scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL)",
            "s->keyed_mixer_nonzero_latched=1u",
            "s->keyed_tl_not_ff_latched=1u",
        ),
        "SDDRV210 R4 keyed runtime",
    )

    main = _r3._sddrv._base._file(
        root, _r3._sddrv._base._MAIN, "SDDRV210 R4 keyed probe main"
    ).read_text(encoding="utf-8", errors="strict")
    _r3._sddrv._base._require_source_anchors(
        main,
        (
            '"KS:"',
            "latched_keyed_scsp_slot",
            "latched_keyed_scsp_control",
            "latched_keyed_scsp_sample_address_low",
            "latched_keyed_scsp_total_level",
            "latched_keyed_scsp_mixer",
        ),
        "SDDRV210 R4 keyed HUD",
    )

    return report
