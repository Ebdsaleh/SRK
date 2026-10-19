from pathlib import Path

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_volume as volume
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe import (
    DIRECT_MIDI_STATUS_ADDRESS,
    MANAGEMENT2_CHANNEL0_ADDRESS,
    MANAGEMENT2_OFFSET,
    PROBE_MASTER_VOLUME_DEFAULT,
    SCSP_SLOT_ADDRESS,
    SCSP_SLOT_STRIDE,
    SLOT_COUNT,
    SLOT_WORK_ADDRESS,
    SLOT_WORK_STRIDE,
    _header,
    _main,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_pre_media import (
    FINAL_BUILD_REPORT_SHA256,
    FINAL_DEPLOYABLE_BIN_SHA256,
    FINAL_DEPLOYABLE_CUE_SHA256,
    FINAL_MANIFEST_SHA256,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    _require_final_hash_lock,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_main.c"


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


def _generated():
    families = _families()
    header = _header(
        volume._header(
            sddrv210._header(legacy._header(26610, 10, families.max_bank_bytes))
        )
    )
    runtime = _runtime(
        volume._runtime(
            sddrv210._runtime(legacy._runtime(families))
        )
    )
    main = _main(
        volume._main(
            sddrv210._main(legacy._main(MAIN.read_text(encoding="utf-8")))
        )
    )
    return header, runtime, main


def test_voice_probe_addresses_are_exact_sddrv210_derivations():
    sound_ram = 0x25A00000
    assert DIRECT_MIDI_STATUS_ADDRESS == sound_ram + 0x0700 + 0x84 + 1
    assert MANAGEMENT2_CHANNEL0_ADDRESS == sound_ram + 0x7000 + 0x0400
    assert SLOT_WORK_ADDRESS == sound_ram + 0x7000 + 0x1000
    assert SLOT_WORK_STRIDE == 0x40
    assert SLOT_COUNT == 32
    assert SCSP_SLOT_ADDRESS == 0x25B00000
    assert SCSP_SLOT_STRIDE == 0x20
    assert MANAGEMENT2_OFFSET == 0x0400


def test_voice_probe_defaults_master_volume_to_safe_five_without_removing_live_control():
    _, runtime, _ = _generated()
    assert PROBE_MASTER_VOLUME_DEFAULT == 5
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_MIN 0u" in runtime
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_MAX 15u" in runtime
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT 5u" in runtime
    assert "SND_SetTlVl((SndTlVl)state->master_volume)" in runtime


def test_voice_probe_samples_driver_management_and_slot_work_read_only():
    header, runtime, _ = _generated()
    for field in (
        "direct_midi_status",
        "driver_program",
        "driver_bank_address",
        "midi_master_volume",
        "midi_volume",
        "midi_expression",
        "noteon_master_volume",
        "total_volume",
        "active_slot_count",
        "active_slot_work_index",
        "active_scsp_slot",
        "slot_management",
        "slot_layer_address",
        "scsp_control",
        "scsp_sample_address_low",
        "scsp_total_level",
        "scsp_mixer",
    ):
        assert field in header

    for required in (
        "SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS 0x25A00785UL",
        "SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS 0x25A07400UL",
        "SRK_SBL_CAL_SLOT_WORK_ADDRESS 0x25A08000UL",
        "SRK_SBL_CAL_SLOT_WORK_STRIDE 0x40UL",
        "SRK_SBL_CAL_SLOT_COUNT 32u",
        "SRK_SBL_CAL_SCSP_SLOT_ADDRESS 0x25B00000UL",
        "SRK_SBL_CAL_SCSP_SLOT_STRIDE 0x20UL",
        "SRK_SBL_CAL_MANAGEMENT2_OFFSET 0x0400u",
        "SRK_SBL_CAL_SLOT_NOTE_ON_MASK 0x08u",
        "srk_cal_probe_voice",
        "srk_cal_probe_be16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET",
        "s->active_scsp_slot=s->slot_flag1&0x1Fu",
        "s->slot_layer_address=(unsigned long)srk_cal_probe_be32(w+0x08UL)",
    ):
        assert required in runtime

    # This probe is observational: its generated helper contains no assignment
    # through a volatile Sound-RAM/SCSP pointer.
    assert "*(volatile Uint8 *)address=" not in runtime
    assert "*(volatile Uint16 *)address=" not in runtime


def test_voice_probe_hud_exposes_driver_and_scsp_allocation_boundary():
    _, _, main = _generated()
    for required in (
        '"M2 S:"',
        '"Bank:"',
        '"Vol M/V/E/N/T"',
        '"Slots:"',
        '"HW:"',
        '"F2:"',
        '"LY:"',
        '"KX:"',
        '"SA:"',
        '"TL:"',
        '"MX:"',
    ):
        assert required in main


def test_voice_probe_manifest_records_exact_read_only_contract():
    document = _telemetry_manifest(
        volume._telemetry_manifest(
            sddrv210._telemetry_manifest(
                {"policy": {}, "sbl_midi_calibration": {"telemetry": {}}}
            )
        )
    )
    assert document["policy"]["sddrv210_telemetry_contract"] is True
    assert document["policy"]["sddrv210_master_volume_control"] is True
    assert document["policy"]["sddrv210_voice_allocation_probe"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["master_volume_default"] == 5
    assert telemetry["direct_midi_management"] == 2
    assert telemetry["direct_midi_channel"] == 0
    assert telemetry["direct_midi_status_address"] == "0x25A00785"
    assert telemetry["management2_channel0_address"] == "0x25A07400"
    assert telemetry["slot_work_address"] == "0x25A08000"
    assert telemetry["scsp_slot_address"] == "0x25B00000"
    assert telemetry["voice_probe_is_read_only"] is True


def test_r1_voice_probe_remains_versioned_behind_velocity_level_seed_keyed_redteam_and_wordbus_probes():
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
    wordbus = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_wordbus.py"
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
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe as _probe"
        in wordbus
    )


def test_voice_probe_guard_has_separate_destination_and_locks_exact_build():
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VOICE-PROBE"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VOICE-PROBE"
    assert FINAL_MANIFEST_SHA256 == (
        "a84ce1e42d6b0db66a667da53ae91d169b70362dacf3e15c07c06b5482766a8b"
    )
    assert FINAL_BUILD_REPORT_SHA256 == (
        "fe47f189689d2580c6ec89c7e860dac2151c2d14be929de07d34aa84106653e7"
    )
    assert FINAL_DEPLOYABLE_BIN_SHA256 == (
        "539251c5552eb38075c1be14fea5817cc796f64bd2513cddc7353e8c0ca5f7b3"
    )
    assert FINAL_DEPLOYABLE_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )
    assert EXPECTED_MANIFEST_SHA256 == FINAL_MANIFEST_SHA256
    assert EXPECTED_BUILD_REPORT_SHA256 == FINAL_BUILD_REPORT_SHA256
    assert EXPECTED_BIN_SHA256 == FINAL_DEPLOYABLE_BIN_SHA256
    assert EXPECTED_CUE_SHA256 == FINAL_DEPLOYABLE_CUE_SHA256
    assert _require_final_hash_lock() == (
        FINAL_MANIFEST_SHA256,
        FINAL_BUILD_REPORT_SHA256,
        FINAL_DEPLOYABLE_BIN_SHA256,
        FINAL_DEPLOYABLE_CUE_SHA256,
    )
