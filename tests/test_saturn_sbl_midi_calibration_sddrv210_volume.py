from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_volume_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationSddrv210VolumeGuardedDeploymentError,
    _require_final_hash_lock,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_volume import (
    MASTER_VOLUME_DEFAULT,
    MASTER_VOLUME_MAX,
    MASTER_VOLUME_MIN,
    _header,
    _main,
    _runtime,
    _telemetry_manifest,
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


def test_sddrv210_volume_contract_uses_exact_driver_master_volume_range():
    assert MASTER_VOLUME_MIN == 0
    assert MASTER_VOLUME_MAX == 15
    assert MASTER_VOLUME_DEFAULT == 15


def test_sddrv210_volume_runtime_defaults_to_max_and_updates_live():
    families = _families()
    header = _header(
        sddrv210._header(legacy._header(26610, 10, families.max_bank_bytes))
    )
    runtime = _runtime(sddrv210._runtime(legacy._runtime(families)))

    assert "unsigned int master_volume;" in header
    assert "runtime_adjust_volume" in header
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_MIN 0u" in runtime
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_MAX 15u" in runtime
    assert "#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT 15u" in runtime
    assert "s->master_volume=SRK_SBL_CAL_MASTER_VOLUME_DEFAULT;" in runtime
    assert "SND_SetTlVl(15)" not in runtime
    assert (
        "result=SND_SetTlVl((SndTlVl)srk_cal_state->master_volume);"
        in runtime
    )
    assert (
        "result=SND_SetTlVl((SndTlVl)state->master_volume);"
        in runtime
    )
    assert "if(next<(int)SRK_SBL_CAL_MASTER_VOLUME_MIN)" in runtime
    assert "if(next>(int)SRK_SBL_CAL_MASTER_VOLUME_MAX)" in runtime

    move = runtime.index("SND_MoveData((Uint16 *)srk_cal_family")
    mix = runtime.index("SND_ChgMix(0,0)")
    volume = runtime.index(
        "SND_SetTlVl((SndTlVl)srk_cal_state->master_volume)"
    )
    bank = runtime.index(
        "srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,SRK_SBL_CAL_CHANNEL,"
        "SRK_SBL_CAL_BANK_CONTROLLER,0u)"
    )
    program = runtime.index(
        "srk_cal_send(SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,"
        "(Uint8)voice,0u)"
    )
    assert move < mix < volume < bank < program


def test_sddrv210_volume_main_maps_dpad_up_down_and_displays_level():
    generated = _main(
        sddrv210._main(legacy._main(MAIN.read_text(encoding="utf-8")))
    )

    for required in (
        "Master volume:",
        "UP/DOWN Master volume",
        "SRK_DIAG_BUTTON_UP",
        "SRK_DIAG_BUTTON_DOWN",
        "&srk_midi_calibration_runtime,1",
        "&srk_midi_calibration_runtime,-1",
        "master_volume",
    ):
        assert required in generated


def test_sddrv210_volume_manifest_records_control_contract():
    document = _telemetry_manifest(
        sddrv210._telemetry_manifest(
            {"policy": {}, "sbl_midi_calibration": {"telemetry": {}}}
        )
    )
    assert document["policy"]["sddrv210_telemetry_contract"] is True
    assert document["policy"]["sddrv210_master_volume_control"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["master_volume_min"] == 0
    assert telemetry["master_volume_max"] == 15
    assert telemetry["master_volume_default"] == 15
    assert telemetry["master_volume_control"] == "DPAD_UP_DOWN"
    assert telemetry["master_volume_command"] == "SND_SetTlVl"


def test_current_candidate_routes_through_volume_layer_without_rewriting_old_sddrv210():
    source = (
        ROOT
        / "src"
        / "rikai_kotoba"
        / "hardware"
        / "saturn"
        / "sbl_midi_calibration_candidate_contract.py"
    ).read_text(encoding="utf-8")
    assert (
        "from . import sbl_midi_calibration_sddrv210_volume as _sddrv210_volume"
        in source
    )
    assert (
        "return _sddrv210_volume.build_saturn_sbl_midi_calibration_candidate("
        in source
    )
    assert (
        "return _legacy_candidate.build_saturn_sbl_midi_calibration_candidate("
        in source
    )


def test_sddrv210_volume_guard_is_new_destination_and_fails_closed_before_build_hashes():
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT-SDDRV210-VOLUME"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT-SDDRV210-VOLUME"
    assert EXPECTED_MANIFEST_SHA256 is None
    assert EXPECTED_BUILD_REPORT_SHA256 is None
    assert EXPECTED_BIN_SHA256 is None
    assert EXPECTED_CUE_SHA256 is None
    with pytest.raises(
        SaturnSblMidiCalibrationSddrv210VolumeGuardedDeploymentError,
        match="intentionally blocked",
    ):
        _require_final_hash_lock()
