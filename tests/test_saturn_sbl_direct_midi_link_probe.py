from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_direct_midi_link_probe import (
    _direct_midi_resolved,
    _link_argv,
    _undefined_symbols_from_objdump,
    accepted_saturn_sbl_direct_midi_link_hashes,
)


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_sbl_direct_midi.c"
_HEADER = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_sbl_direct_midi.h"


def test_link_gate_pins_the_eridu_accepted_compiler_inputs():
    hashes = accepted_saturn_sbl_direct_midi_link_hashes()

    import hashlib

    assert hashlib.sha256(_SOURCE.read_bytes()).hexdigest() == hashes["source"]
    assert hashlib.sha256(_HEADER.read_bytes()).hexdigest() == hashes["adapter_header"]
    assert hashes["sega_header"] == (
        "17e74a4ead1f93f31997755d1a5f8bd6df80bf571d4f5201859d9141d07f9d7e"
    )
    assert hashes["sega_library"] == (
        "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
    )


def test_relocatable_link_uses_only_exact_sound_library_and_no_default_runtime():
    argv = _link_argv(
        Path("C:/tool/sh-elf-gcc.exe"),
        Path("adapter.o"),
        Path("C:/sdk/LIB_ELF/sega_snd.a"),
        Path("linked.o"),
    )

    assert argv == (
        "C:/tool/sh-elf-gcc.exe",
        "-nostdlib",
        "-m2",
        "-Wl,-r",
        "-o",
        "linked.o",
        "adapter.o",
        "C:/sdk/LIB_ELF/sega_snd.a",
    )
    assert "-lgcc" not in argv
    assert all("sega_sat" not in item.casefold() for item in argv)
    assert all("segadgfs" not in item.casefold() for item in argv)


def test_objdump_parser_extracts_only_undefined_symbols():
    output = """
SYMBOL TABLE:
00000000 g     F .text  00000020 _SND_CtrlDirMidi
00000000         *UND*  00000000 _DMA_CpuStart
00000000         *UND*  00000000 ___ashlsi3
00000000         *UND*  00000000 _DMA_CpuStart
"""
    assert _undefined_symbols_from_objdump(output) == (
        "___ashlsi3",
        "_DMA_CpuStart",
    )


def test_direct_midi_resolution_tolerates_elf_leading_underscore():
    assert _direct_midi_resolved(("_DMA_CpuStart", "___ashlsi3"))
    assert not _direct_midi_resolved(("_SND_CtrlDirMidi",))
    assert not _direct_midi_resolved(("SND_CtrlDirMidi",))
