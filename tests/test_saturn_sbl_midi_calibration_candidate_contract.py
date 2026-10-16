from __future__ import annotations

from pathlib import Path
import tempfile

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate_contract import (
    _CURRENT_DIAGNOSTIC_FILES,
    _build_log_tail,
    _legacy_c_text,
    _normalize_staged_legacy_sources,
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
            source_bytes = source.read_bytes()
            generated_bytes = generated.read_bytes()
            assert generated.is_file()
            assert generated_bytes == _legacy_c_text(source_bytes)
            assert generated_bytes.endswith(b"\n")


def test_audio_header_source_is_terminated_for_legacy_sh_gcc():
    payload = (_DIAGNOSTICS / "srk_diag_audio.h").read_bytes()
    assert payload.endswith(b"\n")


def test_legacy_c_text_repairs_only_missing_final_newline():
    assert _legacy_c_text(b"already\n") == b"already\n"
    assert _legacy_c_text(b"missing") == b"missing\n"


def test_staged_legacy_source_normalizer_covers_baseline_sources_too():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_root = Path(temp_dir)
        (source_root / "baseline.c").write_bytes(b"int x;")
        (source_root / "baseline.h").write_bytes(b"#define X 1")
        (source_root / "startup.S").write_bytes(b"nop")
        (source_root / "ignore.bin").write_bytes(b"not source")

        normalized = _normalize_staged_legacy_sources(source_root)

        assert normalized == ("baseline.c", "baseline.h", "startup.S")
        assert (source_root / "baseline.c").read_bytes().endswith(b"\n")
        assert (source_root / "baseline.h").read_bytes().endswith(b"\n")
        assert (source_root / "startup.S").read_bytes().endswith(b"\n")
        assert (source_root / "ignore.bin").read_bytes() == b"not source"


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
