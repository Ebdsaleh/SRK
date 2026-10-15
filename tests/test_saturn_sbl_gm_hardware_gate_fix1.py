from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn import sbl_gm_hardware_gate as base
from rikai_kotoba.hardware.saturn import sbl_gm_hardware_gate_fix1 as fix1


def test_fix1_reads_screen_marker_from_generated_main_without_changing_inventory_view(tmp_path):
    root = tmp_path / "candidate"
    src = root / "src"
    src.mkdir(parents=True)
    runtime = src / "srk_saturn_runtime.c"
    main = src / "srk_saturn_main.c"
    runtime.write_text("SND_CtrlDirMidi\nSRK_SBL_GM_RECORD_COUNT\n", encoding="utf-8")
    main.write_text("SEGA DIRECT MIDI / REAL GM\n", encoding="utf-8")

    original = base._project_file
    with fix1._correct_marker_scope():
        marker_view = base._project_file(root, base._RUNTIME, "candidate runtime")
        text = marker_view.read_text(encoding="utf-8", errors="strict")
        assert "SND_CtrlDirMidi" in text
        assert "SEGA DIRECT MIDI / REAL GM" in text

        inventory_path = base._project_file(root, base._RUNTIME, "generated input")
        assert isinstance(inventory_path, Path)
        assert inventory_path == runtime
        assert "SEGA DIRECT MIDI / REAL GM" not in inventory_path.read_text(encoding="utf-8")

    assert base._project_file is original


def test_fix1_preserves_hardware_confirmation_contract():
    assert fix1.CONFIRMATION_TOKEN == base.CONFIRMATION_TOKEN
    assert fix1.DEFAULT_DESTINATION_NAME == base.DEFAULT_DESTINATION_NAME
