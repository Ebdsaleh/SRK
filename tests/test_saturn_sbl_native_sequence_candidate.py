from rikai_kotoba.hardware.saturn.sbl_native_sequence_candidate import (
    _area_map,
    _native_main,
    _runtime,
)


def test_native_candidate_area_map_has_tone_drum_and_sequence_areas():
    payload, drum_start, sequence_start = _area_map(0x1000, 0x0800, 0x0400)

    assert drum_start == 0x0C000
    assert sequence_start == 0x0C800
    assert len(payload) == 26
    assert payload == bytes.fromhex(
        "00 00 B0 00 00 00 10 00 "
        "01 00 C0 00 00 00 08 00 "
        "10 00 C8 00 00 00 04 00 "
        "FF FF"
    )


def test_native_candidate_runtime_uses_sega_sequence_startup_not_direct_midi():
    source = _runtime()

    assert "SND_ChgMap(0)" in source
    assert "SND_MoveData((Uint16 *)tone" in source
    assert "SND_MoveData((Uint16 *)drum" in source
    assert "SND_MoveData((Uint16 *)sequence" in source
    assert "SND_KD_SEQ,0" in source
    assert "SND_StartSeq(1,0,0,1)" in source
    assert "SND_GetSeqStat(&stat,1)" in source
    assert "SND_GetSeqPlayPos(&pos,1)" in source
    assert "SND_StopSeq(1)" in source
    assert "SND_ChgMix" not in source
    assert "SND_SetTlVl" not in source
    assert "SND_CtrlDirMidi" not in source
    assert "srk_saturn_sbl_direct_midi" not in source


def test_native_candidate_presentation_drops_direct_midi_language():
    generic = '''#include "srk_saturn_host.h"\nstatic SRK_SATURN_HOST_STATE srk_host_state;\nint main(void){\n    srk_diag_app_reset(&srk_app);\n    for (;;) {\n        srk_diag_app_frame(&srk_app, &srk_host);\n    }\n}\n'''
    source = _native_main(generic)

    assert "SEGA NATIVE SEQUENCE / REAL GM" in source
    assert "Position:" in source
    assert "Drv status:" in source
    assert "PASS: native sequence completed" in source
    assert "Space Spectre via SDDRV sequencer" in source
    assert "SEGA DIRECT MIDI / REAL GM" not in source
    assert "accepted 9154 events" not in source
