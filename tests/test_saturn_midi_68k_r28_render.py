"""Regression coverage for the R28 resident renderer recursion fix."""

from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r26_physical_candidate_full_build_gate as r26_gate
from rikai_kotoba.hardware.saturn.midi_68k_r28_full_build_gate import (
    _patched_r28_gate,
)


def test_r28_gate_renderers_do_not_reenter_the_r27_builder():
    with _patched_r28_gate(release_rate=16) as image:
        header = r26_gate.render_srk_saturn_midi_68k_r26_resident_audio_service_header(
            release_rate=16
        )
        source = r26_gate.render_srk_saturn_midi_68k_r26_resident_audio_service_source(
            release_rate=16
        )

        assert f"#define SRK_MIDI_68K_R26_PROGRAM_WORD_COUNT {image.word_count}u" in header
        assert f"#define SRK_MIDI_68K_R26_PROGRAM_BYTE_SIZE {image.byte_size}u" in header
        assert "const unsigned short srk_saturn_midi_68k_r26_resident_audio_service_program[]" in source
        assert source.count("0x") >= image.word_count
