"""Read-only pre-media audit for the SDDRV210 R2 word-bus voice probe."""

from __future__ import annotations

from pathlib import Path

from . import sbl_midi_calibration_sddrv210_voice_probe_pre_media as _r1
from .sbl_midi_calibration_sddrv210_voice_probe_wordbus import (
    BANK_INIT_DEFAULT_VOLUME,
    WORD_BUS_ACCESS,
)


SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusPreMediaError = (
    _r1.SaturnSblMidiCalibrationSddrv210VoiceProbePreMediaError
)


def audit_sddrv210_voice_probe_wordbus_pre_media(project_directory):
    report = _r1.audit_sddrv210_voice_probe_pre_media(project_directory)

    root = Path(project_directory).expanduser().resolve(strict=True)
    manifest_path = _r1._sddrv._base._file(
        root, _r1._sddrv._base._MANIFEST, "SDDRV210 word-bus probe manifest"
    )
    manifest = _r1._sddrv._base._load_json(
        manifest_path, "SDDRV210 word-bus probe manifest"
    )

    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_voice_probe_word_bus") is not True:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusPreMediaError(
            "word-bus probe manifest policy is missing"
        )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusPreMediaError(
            "word-bus probe telemetry manifest record is missing"
        )

    expected = {
        "voice_probe_revision": "R2_WORDBUS",
        "sound_ram_access": WORD_BUS_ACCESS,
        "bank_init_default_volume_expected": BANK_INIT_DEFAULT_VOLUME,
        "byte_fields_via_aligned_word_read": True,
        "u32_fields_via_two_word_read": True,
    }
    for key, wanted in expected.items():
        _r1._sddrv._base._expect(
            telemetry.get(key), wanted, f"word-bus probe telemetry {key}"
        )

    runtime = _r1._sddrv._base._file(
        root, _r1._sddrv._base._RUNTIME, "SDDRV210 word-bus probe runtime"
    ).read_text(encoding="utf-8", errors="strict")

    _r1._sddrv._base._require_source_anchors(
        runtime,
        (
            "static Uint16 srk_cal_probe_word16(Uint32 address)",
            "return *(volatile Uint16 *)(address&~1UL)",
            "static Uint8 srk_cal_probe_u8(Uint32 address)",
            "(address&1UL)?(w&0x00FFu):(w>>8)",
            "static Uint16 srk_cal_probe_u16(Uint32 address)",
            "static Uint32 srk_cal_probe_u32(Uint32 address)",
            "return ((Uint32)p[0]<<16)|(Uint32)p[1]",
            "srk_cal_probe_u16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET",
            "srk_cal_probe_u32(w+0x08UL)",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x10UL",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x12UL",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x14UL",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x18UL",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x1AUL",
        ),
        "SDDRV210 R2 word-bus probe runtime",
    )

    if "volatile Uint8 *" in runtime:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusPreMediaError(
            "R2 probe regressed to raw byte-pointer Sound-RAM access"
        )
    if "srk_cal_probe_be16" in runtime or "srk_cal_probe_be32" in runtime:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusPreMediaError(
            "R2 probe retained R1 byte-composed Sound-RAM helpers"
        )

    return report
