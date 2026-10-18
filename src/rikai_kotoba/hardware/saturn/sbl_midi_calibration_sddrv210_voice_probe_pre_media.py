"""Read-only audit for the SDDRV210 voice-allocation probe candidate."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from . import sbl_midi_calibration_sddrv210_pre_media as _sddrv
from . import sbl_midi_calibration_sddrv210_volume_pre_media as _volume_pre
from .sbl_midi_calibration_sddrv210_voice_probe import (
    DIRECT_MIDI_STATUS_ADDRESS,
    MANAGEMENT2_CHANNEL0_ADDRESS,
    MANAGEMENT2_OFFSET,
    PROBE_MASTER_VOLUME_DEFAULT,
    SCSP_SLOT_ADDRESS,
    SCSP_SLOT_STRIDE,
    SLOT_COUNT,
    SLOT_WORK_ADDRESS,
    SLOT_WORK_STRIDE,
)


SaturnSblMidiCalibrationSddrv210VoiceProbePreMediaError = (
    _sddrv.SaturnSblMidiCalibrationSddrv210PreMediaError
)


@contextmanager
def _probe_base_contract():
    with _volume_pre._volume_base_contract():
        yield


def audit_sddrv210_voice_probe_pre_media(project_directory):
    with _probe_base_contract():
        report = _sddrv.audit_sddrv210_midi_calibration_pre_media(project_directory)

    root = Path(project_directory).expanduser().resolve(strict=True)
    manifest_path = _sddrv._base._file(
        root, _sddrv._base._MANIFEST, "SDDRV210 voice-probe project manifest"
    )
    manifest = _sddrv._base._load_json(
        manifest_path, "SDDRV210 voice-probe project manifest"
    )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbePreMediaError(
            "voice-probe manifest policy is missing"
        )
    for key in (
        "sddrv210_telemetry_contract",
        "sddrv210_master_volume_control",
        "sddrv210_voice_allocation_probe",
    ):
        if policy.get(key) is not True:
            raise SaturnSblMidiCalibrationSddrv210VoiceProbePreMediaError(
                f"voice-probe manifest policy is missing {key}"
            )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbePreMediaError(
            "SDDRV210 voice-probe telemetry manifest record is missing"
        )
    expected = {
        "master_volume_min": 0,
        "master_volume_max": 15,
        "master_volume_default": PROBE_MASTER_VOLUME_DEFAULT,
        "master_volume_control": "DPAD_UP_DOWN",
        "master_volume_command": "SND_SetTlVl",
        "direct_midi_management": 2,
        "direct_midi_channel": 0,
        "direct_midi_status_address": f"0x{DIRECT_MIDI_STATUS_ADDRESS:08X}",
        "management2_channel0_address": f"0x{MANAGEMENT2_CHANNEL0_ADDRESS:08X}",
        "slot_work_address": f"0x{SLOT_WORK_ADDRESS:08X}",
        "slot_work_stride_bytes": SLOT_WORK_STRIDE,
        "slot_count": SLOT_COUNT,
        "scsp_slot_address": f"0x{SCSP_SLOT_ADDRESS:08X}",
        "scsp_slot_stride_bytes": SCSP_SLOT_STRIDE,
        "management2_offset": f"0x{MANAGEMENT2_OFFSET:04X}",
        "slot_note_on_flag_mask": "0x08",
        "slot_key_on_flag_mask": "0x02",
        "voice_probe_is_read_only": True,
    }
    for key, wanted in expected.items():
        _sddrv._base._expect(telemetry.get(key), wanted, f"voice-probe telemetry {key}")

    runtime = _sddrv._base._file(
        root, _sddrv._base._RUNTIME, "SDDRV210 voice-probe runtime"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        runtime,
        (
            "SRK_SBL_CAL_MASTER_VOLUME_DEFAULT 5u",
            "SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS 0x25A00785UL",
            "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS 0x25A07400UL",
            "SRK_SBL_CAL_SLOT_WORK_ADDRESS 0x25A08000UL",
            "SRK_SBL_CAL_SLOT_WORK_STRIDE 0x40UL",
            "SRK_SBL_CAL_SCSP_SLOT_ADDRESS 0x25B00000UL",
            "SRK_SBL_CAL_MANAGEMENT2_OFFSET 0x0400u",
            "srk_cal_probe_voice",
            "s->driver_bank_address",
            "s->active_slot_count",
            "s->slot_layer_address",
            "s->scsp_control",
            "s->scsp_total_level",
            "s->scsp_mixer",
        ),
        "SDDRV210 voice-allocation probe runtime",
    )
    main = _sddrv._base._file(
        root, _sddrv._base._MAIN, "SDDRV210 voice-probe main"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        main,
        (
            '"M2 S:"',
            '"Bank:"',
            '"Vol M/V/E/N/T"',
            '"Slots:"',
            '"LY:"',
            '"KX:"',
            '"SA:"',
            '"TL:"',
            '"MX:"',
        ),
        "SDDRV210 voice-allocation probe HUD",
    )
    return report
