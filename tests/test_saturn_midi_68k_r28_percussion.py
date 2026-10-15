"""Regression tests for R28 percussion fidelity pass 1."""

from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r27_resident_audio_service as r27
from rikai_kotoba.hardware.saturn import midi_68k_r26_physical_candidate_full_build_gate as r26_gate
from rikai_kotoba.hardware.saturn.midi_68k_r24_pitch import (
    build_saturn_midi_68k_r24_pitch_table,
)
from rikai_kotoba.hardware.saturn.midi_68k_r27_fidelity_bank import (
    SATURN_MIDI_68K_R27_DRUM_CYMBAL,
    SATURN_MIDI_68K_R27_DRUM_HIHAT,
    SATURN_MIDI_68K_R27_DRUM_KICK,
    SATURN_MIDI_68K_R27_DRUM_SNARE,
    build_srk_saturn_midi_68k_r27_timbre_bank,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_full_build_gate import (
    _patched_r28_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_percussion_bank import (
    SATURN_MIDI_68K_R28_AUDIO_DATA_END,
    SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_R28_DRUM_LOOP_END,
    SATURN_MIDI_68K_R28_DRUM_LOOP_START,
    SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD,
    SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS,
    build_srk_saturn_midi_68k_r28_percussion_pitch_table,
    build_srk_saturn_midi_68k_r28_timbre_bank,
    srk_saturn_midi_68k_r28_percussion_pitch_note,
    validate_srk_saturn_midi_68k_r28_percussion_layout,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_physical_candidate import (
    derive_r28_percussion_candidate_main,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_resident_audio_service import (
    build_srk_saturn_midi_68k_r28_resident_audio_service_image,
    validate_srk_saturn_midi_68k_r28_resident_audio_layout,
)


def test_r28_keeps_r27_melodic_bank_and_replaces_only_four_drums():
    r27_bank = build_srk_saturn_midi_68k_r27_timbre_bank()
    r28_bank = build_srk_saturn_midi_68k_r28_timbre_bank()
    assert len(r27_bank) == len(r28_bank) == 20
    for index in range(16):
        assert r28_bank[index] == r27_bank[index]

    for index in (
        SATURN_MIDI_68K_R27_DRUM_KICK,
        SATURN_MIDI_68K_R27_DRUM_SNARE,
        SATURN_MIDI_68K_R27_DRUM_HIHAT,
        SATURN_MIDI_68K_R27_DRUM_CYMBAL,
    ):
        assert r28_bank[index].address == r27_bank[index].address
        assert r28_bank[index].words != r27_bank[index].words
        assert len(r28_bank[index].words) == 101
        assert all(
            word == 0
            for word in r28_bank[index].words[SATURN_MIDI_68K_R28_DRUM_LOOP_START :]
        )


def test_r28_drum_note_selects_instrument_but_not_melodic_pitch():
    pitches = build_saturn_midi_68k_r24_pitch_table()
    table = build_srk_saturn_midi_68k_r28_percussion_pitch_table()
    assert len(table) == 128
    assert srk_saturn_midi_68k_r28_percussion_pitch_note(35) == 45
    assert srk_saturn_midi_68k_r28_percussion_pitch_note(40) == 57
    assert srk_saturn_midi_68k_r28_percussion_pitch_note(42) == 69
    assert srk_saturn_midi_68k_r28_percussion_pitch_note(51) == 57
    assert table[35] == pitches[45]
    assert table[40] == pitches[57]
    assert table[42] == pitches[69]
    assert table[51] == pitches[57]
    assert table[35] != pitches[35]
    assert table[40] != pitches[40]
    assert table[42] != pitches[42]
    assert table[51] != pitches[51]


def test_r28_uses_silent_normal_loop_tail_without_moving_program():
    validate_srk_saturn_midi_68k_r28_percussion_layout()
    validate_srk_saturn_midi_68k_r28_resident_audio_layout()
    assert SATURN_MIDI_68K_R28_DRUM_LOOP_START == 96
    assert SATURN_MIDI_68K_R28_DRUM_LOOP_END == 100
    assert SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS == 0x3F00
    assert SATURN_MIDI_68K_R28_AUDIO_DATA_END == 0x4000


def test_r28_drum_telemetry_uses_only_free_globals_after_fix1_scratch():
    assert SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD == 24
    assert SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD == 25
    assert 23 < SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD
    assert SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD < 32


def test_r28_image_is_deterministic_changed_and_restores_r27_hooks():
    before_init = r27._emit_r27_initialization
    before_key = r27._emit_r27_key_on_slot
    r27_image = r27.build_srk_saturn_midi_68k_r27_resident_audio_service_image(
        release_rate=16
    )
    first = build_srk_saturn_midi_68k_r28_resident_audio_service_image(
        release_rate=16
    )
    second = build_srk_saturn_midi_68k_r28_resident_audio_service_image(
        release_rate=16
    )
    assert first.sha256 == second.sha256
    assert first.words == second.words
    assert first.sha256 != r27_image.sha256
    assert r27._emit_r27_initialization is before_init
    assert r27._emit_r27_key_on_slot is before_key


def test_r28_gate_is_scoped_and_preserves_stream_contract():
    original_build = r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image
    original_main = r26_gate.derive_r26_double_impact_candidate_main
    with _patched_r28_gate(release_rate=16) as image:
        assert (
            r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image
            is build_srk_saturn_midi_68k_r28_resident_audio_service_image
        )
        assert (
            r26_gate.derive_r26_double_impact_candidate_main
            is derive_r28_percussion_candidate_main
        )
        assert r26_gate.ACCEPTED_R26_IMAGE_SHA256 == image.sha256
        assert r26_gate.ACCEPTED_R26_RECORDS == 9154
        assert r26_gate.ACCEPTED_R26_BATCHES == 287
        assert r26_gate.ACCEPTED_R26_BUSY == 0
    assert (
        r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image
        is original_build
    )
    assert r26_gate.derive_r26_double_impact_candidate_main is original_main


def test_r28_candidate_subtitle_is_unambiguous():
    import rikai_kotoba.hardware.saturn.midi_68k_r28_physical_candidate as candidate

    assert candidate._R28_SUBTITLE == "Space Spectre R28 P1 - 9154 / 16v"
