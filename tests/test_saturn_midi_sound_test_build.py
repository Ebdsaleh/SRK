from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn import standalone_build


def test_midi_sound_test_source_is_compiled_into_standalone_diagnostics():
    source = "srk_diag_midi_test.c"
    assert source in standalone_build._C_SOURCES
    assert f"build/{Path(source).stem}.o" in standalone_build._OBJECTS
