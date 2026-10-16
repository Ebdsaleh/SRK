from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate import (
    _header,
    _main,
    _runtime,
)


_ROOT = Path(__file__).resolve().parents[1]
_MAIN = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_main.c"


def test_generated_runtime_initializes_real_sega_sound_environment_only():
    header = _header(4096, 8192, 2048)
    runtime = _runtime()

    assert "SRK_SBL_CAL_DRIVER_BYTES 4096UL" in header
    assert "SRK_SBL_CAL_TONE_BYTES 8192UL" in header
    assert "SRK_SBL_CAL_DRUM_BYTES 2048UL" in header
    assert 'srk_cal_load("SDDRVS.TSK"' in runtime
    assert 'srk_cal_load("SRKMAP.BIN"' in runtime
    assert 'srk_cal_load("SRKGM.BIN"' in runtime
    assert 'srk_cal_load("SRKDRUM.BIN"' in runtime
    assert "SND_Init(&ini);" in runtime
    assert "SND_ChgMap(0)" in runtime
    assert "SND_MoveData((Uint16 *)srk_cal_tone" in runtime
    assert "SND_MoveData((Uint16 *)srk_cal_drum" in runtime
    assert "SND_ChgMix(0,0)" in runtime
    assert "SND_SetTlVl(15)" in runtime

    for forbidden in (
        "Space Spectre",
        "SRK_SBL_GM_RECORD_COUNT",
        "event_index",
        "0x25A00000",
        "0x25B00000",
    ):
        assert forbidden not in runtime


def test_generated_main_separates_sbl_midi_from_raw_scsp_audio_callbacks():
    base = _MAIN.read_text(encoding="utf-8")
    generated = _main(base)

    assert '#include "srk_saturn_sbl_midi_calibration.h"' in generated
    assert '#include "srk_saturn_sbl_midi_calibration_runtime.h"' in generated
    assert "srk_host.present_audio_tone = 0;" in generated
    assert "srk_host.stop_audio = 0;" in generated
    assert "srk_host.read_audio_status = 0;" in generated
    assert "srk_saturn_sbl_midi_calibration_runtime_begin" in generated
    assert "srk_saturn_sbl_midi_calibration_bind(&srk_host);" in generated

    # The reusable diagnostic loop remains the owner of MIDI Test interaction.
    assert generated.count("srk_diag_app_frame(&srk_app, &srk_host);") == 1
    assert "gm_frame" not in generated
