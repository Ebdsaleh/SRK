from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210 import (
    SDDRV210_SHA256,
    SDDRV210_VERSION,
    _header,
    _main,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationSddrv210GuardedDeploymentError,
    _require_final_hash_lock,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_pre_media import (
    TRANSITION_BUILD_REPORT_SHA256,
    TRANSITION_DEPLOYABLE_BIN_SHA256,
    TRANSITION_DEPLOYABLE_CUE_SHA256,
    TRANSITION_MANIFEST_SHA256,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_main.c"


def _families() -> SaturnGmCalibrationFamilyBanks:
    banks = []
    for family in range(16):
        payload = bytes(100 + family)
        banks.append(
            SaturnGmCalibrationFamilyBank(
                family=family,
                filename=f"GMC{family:02d}.BIN",
                programs=tuple(range(family * 8, family * 8 + 8)),
                payload=payload,
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


def test_sddrv210_hash_and_transition_provenance_are_exact():
    assert SDDRV210_VERSION == "2.10"
    assert SDDRV210_SHA256 == (
        "68890ee4a49fd0c341bc3f0a48643e4db4b175df0b0d7dacfeb88306340052b6"
    )
    assert TRANSITION_MANIFEST_SHA256 == (
        "648ee095706c0b81b6e9da4e17351e408391c3878890b6f2ac4b12d8f8cdb2b8"
    )
    assert TRANSITION_BUILD_REPORT_SHA256 == (
        "473239f6fd8d65c8d7438121a2e2822d03f9e03891ebade6114f30741c9ee28c"
    )
    assert TRANSITION_DEPLOYABLE_BIN_SHA256 == (
        "f083a04d0eabd249083539db74f6a55482537e279210ab0a081da84aaf97d0ec"
    )
    assert TRANSITION_DEPLOYABLE_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )


def test_sddrv210_runtime_validates_interface_table_and_history_ring():
    families = _families()
    header = _header(legacy._header(26610, 10, families.max_bank_bytes))
    runtime = _runtime(legacy._runtime(families))

    for field in (
        "interface_valid",
        "history_valid",
        "history_offset_raw",
        "system_information_pointer",
        "host_interface_pointer",
        "area_map_current_pointer",
        "system_interface_work_pointer",
    ):
        assert field in header

    for required in (
        "SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_ADDRESS 0x25A00400UL",
        "SRK_SBL_CAL_HOST_INTERFACE_POINTER_ADDRESS 0x25A00404UL",
        "SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_ADDRESS 0x25A00408UL",
        "SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS 0x25A00412UL",
        "SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_EXPECTED 0x00000440UL",
        "SRK_SBL_CAL_HOST_INTERFACE_POINTER_EXPECTED 0x00000700UL",
        "SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_EXPECTED 0x00000500UL",
        "SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED 0x00000480UL",
        "SRK_SBL_CAL_HISTORY_RING_START 0x0800u",
        "SRK_SBL_CAL_HISTORY_RING_END 0x0FFFu",
        "SRK_SBL_CAL_HISTORY_ENTRY_BYTES 16u",
        "SRK_SBL_CAL_HISTORY_OFFSET_MASK 0x07F0u",
        "SRK_SBL_CAL_HISTORY_OFFSET_MAX 0x0800u",
        "raw>SRK_SBL_CAL_HISTORY_OFFSET_MAX",
        "s->history_valid=(s->interface_valid&&history_valid",
        "s->commands_queued>0UL&&s->history_valid",
    ):
        assert required in runtime

    move = runtime.index("SND_MoveData((Uint16 *)srk_cal_family")
    mix = runtime.index("SND_ChgMix(0,0)")
    volume = runtime.index("SND_SetTlVl(15)")
    bank = runtime.index(
        "srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_BANK_CONTROLLER,0u)"
    )
    program = runtime.index(
        "srk_cal_send(SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u)"
    )
    assert move < mix < volume < bank < program
    assert "SND_StartSeq" not in runtime


def test_sddrv210_main_exposes_all_four_interface_pointers():
    generated = _main(legacy._main(MAIN.read_text(encoding="utf-8")))
    for required in (
        "SDDRV exec:",
        "68K err:",
        "Hist:",
        "400:",
        "404:",
        "408:",
        "412:",
        "interface_valid",
        "history_valid",
    ):
        assert required in generated


def test_sddrv210_manifest_records_exact_telemetry_contract():
    document = _telemetry_manifest(
        {
            "policy": {},
            "sbl_midi_calibration": {
                "telemetry": {
                    "driver_error_address": "0x25A00416",
                    "command_history_offset_address": "0x25A0041A",
                    "cpu_error_address": "0x25A00420",
                }
            },
        }
    )
    assert document["policy"]["sddrv210_telemetry_contract"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["driver_version"] == "2.10"
    assert telemetry["driver_sha256"] == SDDRV210_SHA256
    assert telemetry["command_history_ring_start"] == "0x0800"
    assert telemetry["command_history_ring_end"] == "0x0FFF"
    assert telemetry["command_history_entry_bytes"] == 16
    assert telemetry["command_history_offset_max"] == "0x0800"
    assert telemetry["system_information_pointer_expected"] == "0x00000440"
    assert telemetry["host_interface_pointer_expected"] == "0x00000700"
    assert telemetry["area_map_current_pointer_expected"] == "0x00000500"
    assert telemetry["system_interface_work_pointer_expected"] == "0x00000480"
    assert telemetry["interface_table_must_match_before_execution_proof"] is True


def test_sddrv210_guard_is_versioned_and_fails_closed_until_rebuild_hashes_are_locked():
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT-SDDRV210"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT-SDDRV210"
    assert EXPECTED_MANIFEST_SHA256 is None
    assert EXPECTED_BUILD_REPORT_SHA256 is None
    assert EXPECTED_BIN_SHA256 is None
    assert EXPECTED_CUE_SHA256 is None
    with pytest.raises(
        SaturnSblMidiCalibrationSddrv210GuardedDeploymentError,
        match="intentionally blocked",
    ):
        _require_final_hash_lock()


def test_current_candidate_contract_routes_nonhistorical_builds_through_sddrv210():
    source = (
        ROOT
        / "src"
        / "rikai_kotoba"
        / "hardware"
        / "saturn"
        / "sbl_midi_calibration_candidate_contract.py"
    ).read_text(encoding="utf-8")
    assert "from . import sbl_midi_calibration_sddrv210 as _sddrv210" in source
    assert "return _sddrv210.build_saturn_sbl_midi_calibration_candidate(" in source
    assert "return _legacy_candidate.build_saturn_sbl_midi_calibration_candidate(" in source
