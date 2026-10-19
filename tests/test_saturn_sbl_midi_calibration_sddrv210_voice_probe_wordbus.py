from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_volume as volume
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe as r1
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_wordbus import (
    BANK_INIT_DEFAULT_VOLUME,
    WORD_BUS_ACCESS,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_wordbus_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusGuardedDeploymentError,
    _require_final_hash_lock,
)


ROOT = Path(__file__).resolve().parents[1]


def _families() -> SaturnGmCalibrationFamilyBanks:
    banks = []
    for family in range(16):
        banks.append(
            SaturnGmCalibrationFamilyBank(
                family=family,
                filename=f"GMC{family:02d}.BIN",
                programs=tuple(range(family * 8, family * 8 + 8)),
                payload=bytes(100 + family),
                sha256=f"{family:064x}",
                voices=(),
                velocity_amounts=(0,),
            )
        )
    return SaturnGmCalibrationFamilyBanks(
        source_path=Path("GeneralUser-GS.sf2"),
        source_sha256="0" * 64,
        banks=tuple(banks),
    )


def _r1_runtime() -> str:
    families = _families()
    return r1._runtime(
        volume._runtime(
            sddrv210._runtime(legacy._runtime(families))
        )
    )


def _r2_runtime() -> str:
    return _runtime(_r1_runtime())


def test_wordbus_probe_replaces_raw_sound_ram_byte_access_with_aligned_words():
    runtime = _r2_runtime()

    assert "static Uint16 srk_cal_probe_word16(Uint32 address)" in runtime
    assert "return *(volatile Uint16 *)(address&~1UL);" in runtime
    assert (
        "static Uint8 srk_cal_probe_u8(Uint32 address)"
        "{Uint16 w=srk_cal_probe_word16(address);"
        "return (Uint8)((address&1UL)?(w&0x00FFu):(w>>8));}"
        in runtime
    )
    assert "static Uint16 srk_cal_probe_u16(Uint32 address)" in runtime
    assert "static Uint32 srk_cal_probe_u32(Uint32 address)" in runtime
    assert "return ((Uint32)p[0]<<16)|(Uint32)p[1];" in runtime

    assert "volatile Uint8 *" not in runtime
    assert "srk_cal_probe_be16" not in runtime
    assert "srk_cal_probe_be32" not in runtime


def test_wordbus_probe_uses_word_reads_for_management_and_slot_state():
    runtime = _r2_runtime()

    for required in (
        "srk_cal_probe_u8(SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS)",
        "srk_cal_probe_u8(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x00UL)",
        "srk_cal_probe_u32(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x04UL)",
        "srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x10UL)",
        "srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x12UL)",
        "srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x14UL)",
        "srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x18UL)",
        "srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x1AUL)",
        "srk_cal_probe_u16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET",
        "srk_cal_probe_u32(w+0x08UL)",
    ):
        assert required in runtime


def test_r1_byte_access_is_preserved_as_historical_physical_evidence():
    runtime = _r1_runtime()

    assert "volatile Uint8 *p=(volatile Uint8 *)address" in runtime
    assert "srk_cal_probe_be16" in runtime
    assert "srk_cal_probe_be32" in runtime


def test_wordbus_manifest_records_measurement_correction_and_bank_init_invariant():
    document = _telemetry_manifest(
        r1._telemetry_manifest(
            volume._telemetry_manifest(
                sddrv210._telemetry_manifest(
                    {"policy": {}, "sbl_midi_calibration": {"telemetry": {}}}
                )
            )
        )
    )

    assert document["policy"]["sddrv210_voice_allocation_probe"] is True
    assert document["policy"]["sddrv210_voice_probe_word_bus"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["voice_probe_revision"] == "R2_WORDBUS"
    assert telemetry["sound_ram_access"] == "UINT16_ALIGNED"
    assert telemetry["bank_init_default_volume_expected"] == 0x007F
    assert telemetry["byte_fields_via_aligned_word_read"] is True
    assert telemetry["u32_fields_via_two_word_read"] is True

    assert WORD_BUS_ACCESS == "UINT16_ALIGNED"
    assert BANK_INIT_DEFAULT_VOLUME == 0x007F


def test_r2_wordbus_probe_remains_preserved_behind_velocity_level_seed_keyed_and_redteam_probes():
    source_root = (
        ROOT
        / "src"
        / "rikai_kotoba"
        / "hardware"
        / "saturn"
    )
    contract = (
        source_root / "sbl_midi_calibration_candidate_contract.py"
    ).read_text(encoding="utf-8")
    velocity_sweep = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep.py"
    ).read_text(encoding="utf-8")
    level_seed = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_level_seed.py"
    ).read_text(encoding="utf-8")
    keyed = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_keyed.py"
    ).read_text(encoding="utf-8")
    redteam = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_redteam.py"
    ).read_text(encoding="utf-8")
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep "
        "as _sddrv210_probe"
        in contract
    )
    assert (
        "return _sddrv210_probe.build_saturn_sbl_midi_calibration_candidate("
        in contract
    )
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_level_seed as _r5"
        in velocity_sweep
    )
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_keyed as _r4"
        in level_seed
    )
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_redteam as _r3"
        in keyed
    )
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_wordbus as _r2"
        in redteam
    )


def test_wordbus_guard_is_separate_and_fails_closed_before_r2_hash_lock():
    assert DESTINATION_NAME == (
        "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VOICE-PROBE-WORDBUS"
    )
    assert CONFIRMATION_TOKEN == (
        "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VOICE-PROBE-WORDBUS"
    )
    assert EXPECTED_MANIFEST_SHA256 is None
    assert EXPECTED_BUILD_REPORT_SHA256 is None
    assert EXPECTED_BIN_SHA256 is None
    assert EXPECTED_CUE_SHA256 is None

    with pytest.raises(
        SaturnSblMidiCalibrationSddrv210VoiceProbeWordBusGuardedDeploymentError,
        match="intentionally blocked",
    ):
        _require_final_hash_lock()
