from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_direct_midi_compile_probe import (
    _rank_sdk_path,
    saturn_sbl_direct_midi_compile_flags,
)


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_sbl_direct_midi.c"
_HEADER = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_sbl_direct_midi.h"


def test_compile_flags_match_production_legacy_sh2_policy():
    assert saturn_sbl_direct_midi_compile_flags() == (
        "-Wall",
        "-Werror",
        "-m2",
        "-O0",
        "-ffreestanding",
        "-fno-builtin",
    )


def test_sdk_ranking_prefers_direct_sbl601_segalib_install():
    direct_header = Path("C:/Saturn-Dev/SBL_601/SEGALIB/INCLUDE/SEGA_SND.H")
    copied_header = Path(
        "C:/Saturn-Dev/SaturnOrbit-Inspect/payload/app/SBL_601/SEGALIB/INCLUDE/SEGA_SND.H"
    )
    direct_library = Path("C:/Saturn-Dev/SBL_601/SEGALIB/LIB_ELF/sega_snd.a")
    copied_library = Path(
        "C:/Saturn-Dev/SaturnOrbit-Inspect/payload/app/SBL_601/SEGALIB/LIB_ELF/sega_snd.a"
    )

    assert _rank_sdk_path(direct_header, kind="header") < _rank_sdk_path(
        copied_header, kind="header"
    )
    assert _rank_sdk_path(direct_library, kind="library") < _rank_sdk_path(
        copied_library, kind="library"
    )


def test_c_adapter_is_a_thin_sega_sound_driver_boundary():
    source = _SOURCE.read_text(encoding="utf-8")
    header = _HEADER.read_text(encoding="utf-8")

    assert '#include "sega_snd.h"' in header
    assert "SndRet srk_saturn_sbl_direct_midi(" in header
    assert "return SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2);" in source

    # This backend must not regress into the R26-R28 custom SCSP synthesizer.
    combined = source + "\n" + header
    for forbidden in (
        "0x25A00000",
        "0x25B00000",
        "KYONB",
        "KYONEX",
        "DIPAN",
        "DISDL",
        "MC68EC000",
    ):
        assert forbidden not in combined
