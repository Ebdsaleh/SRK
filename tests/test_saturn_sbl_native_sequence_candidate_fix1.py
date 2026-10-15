from rikai_kotoba.hardware.saturn import sbl_native_sequence_candidate as base
from rikai_kotoba.hardware.saturn import sbl_native_sequence_candidate_fix1 as fix1


def test_fix1_uses_minimum_documented_native_sequence_surface():
    runtime = fix1._patched_runtime()

    assert "SND_MoveData((Uint16 *)sequence" in runtime
    assert "SND_KD_SEQ,0" in runtime
    assert "SND_SetTlVl(15)" in runtime
    assert "SND_StartSeq(1,0,0,1)" in runtime
    assert "SND_GetSeqStat(&stat,1)" in runtime
    assert "SND_StopSeq(1)" in runtime

    assert "SND_GetSeqPlayPos" not in runtime
    assert "SndSeqPlayPos" not in runtime
    assert "SND_CtrlDirMidi" not in runtime


def test_fix1_patch_is_scoped_and_non_recursive():
    original_runtime = base._runtime
    original_main = base._native_main

    with fix1._compatibility_patch():
        assert base._runtime is fix1._patched_runtime
        assert base._native_main is fix1._patched_main
        assert "SND_StartSeq(1,0,0,1)" in base._runtime()

    assert base._runtime is original_runtime
    assert base._native_main is original_main
