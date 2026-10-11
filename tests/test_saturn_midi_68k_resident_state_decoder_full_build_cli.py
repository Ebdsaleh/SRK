"""CLI regression for the Phase-B inert state-decoder full-build gate."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rikai_kotoba.tools.saturn_midi_68k_resident_state_decoder_full_build_gate import main


def test_cli_prints_preserved_r20_and_inert_phase_b_boundaries():
    prepared = SimpleNamespace(
        baseline_root=Path("R20"),
        output_root=Path("PHASE-B"),
        baseline_manifest_sha256="1" * 64,
        baseline_report_sha256="2" * 64,
        baseline_bin_sha256="3" * 64,
        baseline_cue_sha256="4" * 64,
        image_sha256="5" * 64,
        image_word_count=4898,
        image_byte_size=9796,
        program_address=0x4000,
        program_end_address=0x6644,
        source_sha256="6" * 64,
        header_sha256="7" * 64,
        compiler_object_sha256="8" * 64,
        r20_main_sha256="9" * 64,
        r20_menu_sha256="a" * 64,
        runtime_before_sha256="b" * 64,
        runtime_after_sha256="c" * 64,
    )
    build = SimpleNamespace(
        commands=(),
        artifacts=(),
        log_path=Path("build.log"),
        report_path=Path("report.json"),
        successful=True,
    )

    argv = [
        "--baseline-project", "R20",
        "--output", "PHASE-B",
        "--expected-baseline-manifest-sha256", "1" * 64,
        "--expected-baseline-report-sha256", "2" * 64,
        "--expected-baseline-bin-sha256", "3" * 64,
        "--expected-baseline-cue-sha256", "4" * 64,
        "--expected-image-sha256", "5" * 64,
        "--expected-compiler-source-sha256", "6" * 64,
        "--expected-compiler-header-sha256", "7" * 64,
        "--expected-compiler-object-sha256", "8" * 64,
    ]

    output = StringIO()
    with patch(
        "rikai_kotoba.tools.saturn_midi_68k_resident_state_decoder_full_build_gate."
        "run_midi_68k_resident_state_decoder_full_build_gate",
        return_value=SimpleNamespace(prepared=prepared, build=build),
    ):
        with redirect_stdout(output):
            code = main(argv)

    text = output.getvalue()
    assert code == 0
    assert "State decoder words     : 4898" in text
    assert "Dynamic state mutation  : ALL 7 SRKM v1 opcodes" in text
    assert "Existing R20 binding    : PRESERVED" in text
    assert "State decoder linked    : YES" in text
    assert "State decoder installed : NO" in text
    assert "State decoder executed  : NO" in text
    assert "Candidate bound         : NO" in text
    assert "MIDI-driven SCSP note   : NO" in text
    assert "Build-time hardware I/O : NO" in text
    assert "SAROO writes            : NONE" in text
    assert "Result                   : SUCCESS" in text
