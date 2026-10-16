from __future__ import annotations

from pathlib import Path
import tempfile

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate_contract import (
    _CURRENT_DIAGNOSTIC_FILES,
    _build_log_tail,
    _overlay_current_diagnostics,
)


_ROOT = Path(__file__).resolve().parents[1]
_DIAGNOSTICS = _ROOT / "integrations" / "saturn" / "diagnostics"


def test_current_diagnostics_overlay_includes_midi_screen_and_matches_repository():
    assert "srk_diag_app.c" in _CURRENT_DIAGNOSTIC_FILES
    assert "srk_diag_host.h" in _CURRENT_DIAGNOSTIC_FILES
    assert "srk_diag_menu.c" in _CURRENT_DIAGNOSTIC_FILES
    assert "srk_diag_midi_test.c" in _CURRENT_DIAGNOSTIC_FILES
    assert "srk_diag_midi_test.h" in _CURRENT_DIAGNOSTIC_FILES

    with tempfile.TemporaryDirectory() as temp_dir:
        stage = Path(temp_dir) / "stage"
        copied = _overlay_current_diagnostics(stage)

        assert copied == _CURRENT_DIAGNOSTIC_FILES
        for filename in copied:
            generated = stage / "src" / filename
            source = _DIAGNOSTICS / filename
            assert generated.is_file()
            assert generated.read_bytes() == source.read_bytes()


def test_failed_candidate_build_log_tail_is_available_for_console_error():
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        log = output / "SRK_STANDALONE_BUILD_LOG.txt"
        log.write_text(
            "[compile one.c] returncode=0\n\n"
            "[compile calibration.c] returncode=1\n"
            "legacy compiler error: exact failure\n",
            encoding="utf-8",
        )

        tail = _build_log_tail(output)

        assert "compile calibration.c" in tail
        assert "returncode=1" in tail
        assert "legacy compiler error: exact failure" in tail
