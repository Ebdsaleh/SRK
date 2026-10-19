"""Read-only pre-media audit for the REDTEAM-hardened SDDRV210 R3 probe."""

from __future__ import annotations

from pathlib import Path

from . import sbl_midi_calibration_sddrv210_pre_media as _sddrv
from . import sbl_midi_calibration_sddrv210_voice_probe_pre_media as _r1_pre
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
from .sbl_midi_calibration_sddrv210_voice_probe_wordbus import (
    BANK_INIT_DEFAULT_VOLUME,
    WORD_BUS_ACCESS,
)
from .sbl_midi_calibration_sddrv210_voice_probe_redteam import (
    HARDENING_REVISION,
    SCSP_KYONB_MASK,
)


SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError = (
    _sddrv.SaturnSblMidiCalibrationSddrv210PreMediaError
)


def audit_sddrv210_voice_probe_redteam_pre_media(project_directory):
    # Validate the already-proven SDDRV210 + dynamic-volume contract, but do not
    # reuse R1/R2 HUD assertions because R3 intentionally replaces that HUD.
    with _r1_pre._probe_base_contract():
        report = _sddrv.audit_sddrv210_midi_calibration_pre_media(project_directory)

    root = Path(project_directory).expanduser().resolve(strict=True)
    manifest_path = _sddrv._base._file(
        root, _sddrv._base._MANIFEST, "SDDRV210 REDTEAM probe manifest"
    )
    manifest = _sddrv._base._load_json(
        manifest_path, "SDDRV210 REDTEAM probe manifest"
    )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
            "REDTEAM probe manifest policy is missing"
        )
    for key in (
        "sddrv210_telemetry_contract",
        "sddrv210_master_volume_control",
        "sddrv210_voice_allocation_probe",
        "sddrv210_voice_probe_word_bus",
        "sddrv210_voice_probe_redteam_hardened",
    ):
        if policy.get(key) is not True:
            raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
                f"REDTEAM probe manifest policy is missing {key}"
            )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
            "REDTEAM probe telemetry manifest record is missing"
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
        "voice_probe_is_read_only": True,
        "voice_probe_revision": "R2_WORDBUS",
        "sound_ram_access": WORD_BUS_ACCESS,
        "bank_init_default_volume_expected": BANK_INIT_DEFAULT_VOLUME,
        "byte_fields_via_aligned_word_read": True,
        "u32_fields_via_two_word_read": True,
        "voice_probe_hardening": HARDENING_REVISION,
        "allocation_flag_is_not_gate": True,
        "management_scan_independent": True,
        "slot_work_change_latched": True,
        "scsp_scan_independent": True,
        "scsp_change_latched": True,
        "scsp_kyonb_mask": f"0x{SCSP_KYONB_MASK:04X}",
        "scsp_kyonb_latched": True,
        "u32_double_sample_stability": True,
        "status_aligned_word_exposed": True,
        "note_interval_latching": True,
    }
    for key, wanted in expected.items():
        _sddrv._base._expect(
            telemetry.get(key), wanted, f"REDTEAM probe telemetry {key}"
        )

    runtime = _sddrv._base._file(
        root, _sddrv._base._RUNTIME, "SDDRV210 REDTEAM probe runtime"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        runtime,
        (
            "static Uint16 srk_cal_probe_word16(Uint32 address)",
            "return *(volatile Uint16 *)(address&~1UL)",
            "static Uint8 srk_cal_probe_u8(Uint32 address)",
            "(address&1UL)?(w&0x00FFu):(w>>8)",
            "static Uint32 srk_cal_probe_u32_stable(Uint32 address,unsigned int *ok)",
            "for(i=0u;i<4u;i++)",
            "SRK_SBL_CAL_SCSP_KYONB_MASK 0x0800u",
            "srk_cal_probe_capture_baseline",
            "srk_cal_probe_slot_baseline",
            "srk_cal_probe_scsp_baseline",
            "s->probe_bus_sane=(s->midi_master_volume==0x007Fu",
            "srk_cal_probe_u16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET",
            "s->management_match_count++",
            "s->slot_changed_latched=1u",
            "s->scsp_changed_latched=1u",
            "s->scsp_key_latched=1u",
            "srk_cal_probe_capture_baseline(srk_cal_state)",
            "srk_cal_probe_latch_stop(srk_cal_state)",
        ),
        "SDDRV210 R3 REDTEAM runtime",
    )
    if "volatile Uint8 *" in runtime:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
            "R3 probe regressed to raw byte-pointer Sound-RAM access"
        )
    if "static Uint32 srk_cal_probe_u32(Uint32 address)" in runtime:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
            "R3 probe retained obsolete unused R2 u32 helper"
        )
    if "if((f2&SRK_SBL_CAL_SLOT_NOTE_ON_MASK)!=0u)" in runtime:
        raise SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError(
            "R3 probe still gates allocation evidence on the old flag2 bit"
        )

    main = _sddrv._base._file(
        root, _sddrv._base._MAIN, "SDDRV210 REDTEAM probe main"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        main,
        (
            '"BUS:"',
            '"M2:"',
            '"MG:"',
            '"SW:"',
            '"HW:"',
            '"LAT"',
            '"F1:"',
            '"F2:"',
            '"LY:"',
            '"KX:"',
            '"SA:"',
            '"TL:"',
            '"MX:"',
            '"KL"',
        ),
        "SDDRV210 R3 REDTEAM HUD",
    )

    return report
