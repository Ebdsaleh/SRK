from pathlib import Path

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_volume as volume
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe as r1
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_wordbus as r2
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_redteam import (
    HARDENING_REVISION,
    SCSP_KYONB_MASK,
    _header,
    _main,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_redteam_pre_media import (
    FINAL_BUILD_REPORT_SHA256,
    FINAL_DEPLOYABLE_BIN_SHA256,
    FINAL_DEPLOYABLE_CUE_SHA256,
    FINAL_MANIFEST_SHA256,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_redteam_guarded_deployment import (
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
    base_header = r1._header(
        volume._header(
            sddrv210._header(legacy._header(26610, 10, families.max_bank_bytes))
        )
    )
    base_runtime = r2._runtime(
        r1._runtime(
            volume._runtime(
                sddrv210._runtime(legacy._runtime(families))
            )
        )
    )
    base_main = r1._main(
        volume._main(
            sddrv210._main(
                legacy._main(MAIN.read_text(encoding="utf-8"))
            )
        )
    )
    return _header(base_header), _runtime(base_runtime), _main(base_main)


def test_redteam_probe_removes_flag2_as_allocation_gate():
    _, runtime, _ = _generated()
    assert "if((f2&SRK_SBL_CAL_SLOT_NOTE_ON_MASK)!=0u)" not in runtime
    assert (
        "srk_cal_probe_u16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET"
        in runtime
    )
    assert "s->management_match_count++" in runtime


def test_redteam_probe_latches_independent_slot_and_scsp_changes():
    header, runtime, _ = _generated()
    for field in (
        "probe_bus_sane",
        "direct_midi_status_word",
        "management_match_count",
        "slot_changed_latched",
        "scsp_changed_latched",
        "scsp_key_latched",
        "latched_slot_work_index",
        "latched_scsp_slot",
        "latched_slot_layer_address",
        "latched_scsp_control",
    ):
        assert field in header

    for required in (
        "srk_cal_probe_capture_baseline",
        "srk_cal_probe_slot_baseline",
        "srk_cal_probe_scsp_baseline",
        "s->slot_changed_latched=1u",
        "s->scsp_changed_latched=1u",
        "SRK_SBL_CAL_SCSP_KYONB_MASK 0x0800u",
        "s->scsp_key_latched=1u",
        "srk_cal_probe_capture_baseline(srk_cal_state)",
        "srk_cal_probe_latch_stop(srk_cal_state)",
    ):
        assert required in runtime


def test_redteam_probe_keeps_wordbus_and_only_stable_u32_reader():
    _, runtime, _ = _generated()
    assert "volatile Uint8 *" not in runtime
    assert "static Uint16 srk_cal_probe_word16(Uint32 address)" in runtime
    assert "static Uint32 srk_cal_probe_u32(Uint32 address)" not in runtime
    assert "static Uint32 srk_cal_probe_u32_stable(Uint32 address,unsigned int *ok)" in runtime
    assert runtime.count("srk_cal_probe_u32_stable(") >= 3
    assert "for(i=0u;i<4u;i++)" in runtime
    assert "s->bank_read_stable=stable" in runtime
    assert "s->layer_read_stable=stable" in runtime


def test_redteam_probe_has_bank_init_bus_sanity_and_raw_status_word():
    _, runtime, main = _generated()
    assert (
        "s->probe_bus_sane=(s->midi_master_volume==0x007Fu&&"
        "s->midi_volume==0x007Fu&&s->midi_expression==0x007Fu)?1u:0u;"
        in runtime
    )
    assert (
        "s->direct_midi_status_word=(unsigned int)"
        "srk_cal_probe_word16(SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS);"
        in runtime
    )
    for label in ('"BUS:"', '"M2:"', '"MG:"', '"SW:"', '"HW:"', '"LAT"', '"KL"'):
        assert label in main


def test_redteam_manifest_records_independent_evidence_contract():
    document = _telemetry_manifest(
        r2._telemetry_manifest(
            r1._telemetry_manifest(
                volume._telemetry_manifest(
                    sddrv210._telemetry_manifest(
                        {"policy": {}, "sbl_midi_calibration": {"telemetry": {}}}
                    )
                )
            )
        )
    )
    assert document["policy"]["sddrv210_voice_probe_redteam_hardened"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["voice_probe_revision"] == "R2_WORDBUS"
    assert telemetry["voice_probe_hardening"] == HARDENING_REVISION
    assert telemetry["allocation_flag_is_not_gate"] is True
    assert telemetry["management_scan_independent"] is True
    assert telemetry["slot_work_change_latched"] is True
    assert telemetry["scsp_scan_independent"] is True
    assert telemetry["scsp_change_latched"] is True
    assert telemetry["scsp_kyonb_latched"] is True
    assert telemetry["scsp_kyonb_mask"] == f"0x{SCSP_KYONB_MASK:04X}"
    assert telemetry["u32_double_sample_stability"] is True


def test_redteam_guard_is_separate_and_locks_exact_r3_fix1_build():
    assert DESTINATION_NAME == (
        "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VOICE-PROBE-REDTEAM"
    )
    assert CONFIRMATION_TOKEN == (
        "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VOICE-PROBE-REDTEAM"
    )
    assert FINAL_MANIFEST_SHA256 == (
        "203d19d5925d40257b3619ee896bea62f4e03ac24d059152ceb7b6a415fb3656"
    )
    assert FINAL_BUILD_REPORT_SHA256 == (
        "eb65e5b39d62b96db550bbf173cfd0c11ef2f1904f143958b69ceb72b203afa8"
    )
    assert FINAL_DEPLOYABLE_BIN_SHA256 == (
        "27445ee35c639213bc522d6b762728e6321617fd9e9dbc43dc63fb0d9bf8b8f5"
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


def test_redteam_reset_state_is_injected_structurally_once():
    _, runtime, _ = _generated()
    start = runtime.index(
        "void srk_saturn_sbl_midi_calibration_runtime_reset("
        "SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){"
    )
    end = runtime.index(
        "static unsigned int srk_cal_begin(void *context){",
        start,
    )
    reset = runtime[start:end]

    assert reset.count("s->probe_bus_sane=0u;") == 1
    assert "s->slot_changed_latched=0u" in reset
    assert "s->scsp_changed_latched=0u" in reset
    assert "s->scsp_key_latched=0u" in reset
    assert "s->probe_latch_active=0u;srk_cal_probe_latch_active=0u;" in reset
    assert runtime.count("s->probe_bus_sane=0u;") == 1
