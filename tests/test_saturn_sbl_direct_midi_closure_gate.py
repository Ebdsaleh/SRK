from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_direct_midi_closure_gate import (
    closure_link_argv_for_test,
)


_ROOT = Path(__file__).resolve().parents[1]
_RUNTIME = _ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_sbl_runtime.c"


def test_runtime_defines_only_required_c_memory_primitives():
    source = _RUNTIME.read_text(encoding="utf-8")
    assert "void *memcpy(" in source
    assert "void *memset(" in source
    assert "malloc(" not in source
    assert "free(" not in source


def test_closure_link_orders_sound_runtime_and_exact_libgcc():
    compiler = Path("C:/tool/sh-elf-gcc.exe")
    adapter = Path("adapter.o")
    sound = Path("C:/sdk/sega_snd.a")
    runtime = Path("runtime.o")
    libgcc = Path("C:/tool/libgcc.a")
    linked = Path("closed.o")

    argv = closure_link_argv_for_test(
        compiler, adapter, sound, runtime, libgcc, linked
    )

    assert argv == (
        str(compiler),
        "-nostdlib",
        "-m2",
        "-Wl,-r",
        "-o",
        str(linked),
        str(adapter),
        str(sound),
        str(runtime),
        str(libgcc),
    )
    assert argv.index(str(sound)) < argv.index(str(libgcc))


def test_runtime_does_not_reintroduce_custom_scsp_synthesis():
    source = _RUNTIME.read_text(encoding="utf-8")
    for forbidden in (
        "0x25A00000",
        "0x25B00000",
        "KYONB",
        "KYONEX",
        "DIPAN",
        "DISDL",
        "SND_CtrlDirMidi",
    ):
        assert forbidden not in source
