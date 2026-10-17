from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_consolidated import (
    _area_map,
    _header,
    _main,
    _runtime,
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


def test_consolidated_runtime_is_screen_owned_and_family_loaded():
    families = _families()
    header = _header(25488, 10, families.max_bank_bytes)
    runtime = _runtime(families)

    assert "SRK_SBL_CAL_FAMILY_COUNT 16u" in header
    assert "SRK_SBL_CAL_FAMILY_NONE 0xffffu" in header
    assert 'srk_cal_load("SDDRVS.TSK"' in runtime
    assert 'srk_cal_load("SRKMAP.BIN"' in runtime
    assert '"GMC00.BIN"' in runtime
    assert '"GMC15.BIN"' in runtime
    assert "family=program/SRK_SBL_CAL_FAMILY_SIZE" in runtime
    assert "voice=program%SRK_SBL_CAL_FAMILY_SIZE" in runtime
    assert "SND_MoveData((Uint16 *)srk_cal_family" in runtime
    assert "SND_KD_TONE,0" in runtime
    assert "SND_ChgMix(0,0)" in runtime
    assert "SND_SetTlVl(15)" in runtime

    # Match Sega's Direct-MIDI one-shot setup around the resident tone bank:
    # transfer tone -> select mixer -> set total level -> select bank/program.
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

    # Direct MIDI is deliberately not bootstrapped by a dummy sequence.
    assert "SND_StartSeq" not in runtime

    # SND_Init is reachable only from lazy program preparation, not from _main.
    assert "static unsigned int srk_cal_begin(void *context)" in runtime
    assert "if(!srk_cal_begin(context))return 0;" in runtime


def test_consolidated_runtime_exposes_real_68k_execution_telemetry():
    runtime = _runtime(_families())
    assert "0x25A00416UL" in runtime
    assert "0x25A0041AUL" in runtime
    assert "0x25A00420UL" in runtime
    assert "history!=s->history_baseline" in runtime
    assert "s->driver_executed=1u" in runtime
    assert "commands_queued" in runtime
    assert "driver_error" in runtime
    assert "cpu_error" in runtime


def test_consolidated_main_retains_raw_scsp_and_releases_sbl_on_screen_exit():
    generated = _main(MAIN.read_text(encoding="utf-8"))

    assert '#include "srk_saturn_sbl_midi_calibration_runtime.h"' in generated
    assert "srk_saturn_sbl_midi_calibration_runtime_bind(&srk_host" in generated
    assert "srk_saturn_sbl_midi_calibration_runtime_stop" in generated
    assert "srk_saturn_sbl_midi_calibration_runtime_poll" in generated
    assert "srk_cal_frame();" in generated
    assert "SDDRV exec:" in generated
    assert "68K err:" in generated
    assert "Hist:" in generated
    assert "Queued:" in generated
    assert "srk_host.present_audio_tone = 0" not in generated
    assert "srk_host.stop_audio = 0" not in generated
    assert "srk_host.read_audio_status = 0" not in generated
    assert "SND_Init" not in generated
    assert generated.count("srk_diag_app_frame(&srk_app, &srk_host);") == 1


def test_consolidated_area_map_is_single_external_tone_reservation():
    payload = _area_map(0x10000)
    assert len(payload) == 10
    assert payload[-2:] == b"\xFF\xFF"
    assert payload[0] >> 4 == 0
    assert payload[0] & 0x0F == 0
