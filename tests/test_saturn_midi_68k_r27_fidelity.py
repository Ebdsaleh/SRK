"""Regression tests for R27 fidelity pass 1."""

from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r26_resident_audio_service as r26
from rikai_kotoba.hardware.saturn import midi_68k_r26_physical_candidate_full_build_gate as r26_gate
from rikai_kotoba.hardware.saturn.midi_68k_r27_fidelity_bank import (
    SATURN_MIDI_68K_R27_AUDIO_DATA_END,
    SATURN_MIDI_68K_R27_DRUM_CYMBAL,
    SATURN_MIDI_68K_R27_DRUM_HIHAT,
    SATURN_MIDI_68K_R27_DRUM_KICK,
    SATURN_MIDI_68K_R27_DRUM_SNARE,
    SATURN_MIDI_68K_R27_GM_FAMILY_COUNT,
    SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS,
    SATURN_MIDI_68K_R27_TIMBRE_COUNT,
    SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES,
    build_srk_saturn_midi_68k_r27_pan_table,
    build_srk_saturn_midi_68k_r27_percussion_source_table,
    build_srk_saturn_midi_68k_r27_program_source_table,
    build_srk_saturn_midi_68k_r27_timbre_bank,
    srk_saturn_midi_68k_r27_channel_timbre,
    srk_saturn_midi_68k_r27_mixer_word,
    srk_saturn_midi_68k_r27_program_timbre,
)
from rikai_kotoba.hardware.saturn.midi_68k_r27_full_build_gate import _patched_r27_gate
from rikai_kotoba.hardware.saturn.midi_68k_r27_physical_candidate import (
    derive_r27_fidelity_candidate_main,
)
from rikai_kotoba.hardware.saturn.midi_68k_r27_resident_audio_service import (
    build_srk_saturn_midi_68k_r27_resident_audio_service_image,
    validate_srk_saturn_midi_68k_r27_resident_audio_layout,
)


def test_r27_bank_has_16_gm_families_and_four_distinct_drum_classes():
    bank = build_srk_saturn_midi_68k_r27_timbre_bank()
    assert SATURN_MIDI_68K_R27_GM_FAMILY_COUNT == 16
    assert len(bank) == SATURN_MIDI_68K_R27_TIMBRE_COUNT == 20
    assert len({timbre.words for timbre in bank}) == 20
    assert all(len(timbre.words) == 101 for timbre in bank)
    assert all(timbre.words[0] == timbre.words[-1] for timbre in bank)

    assert srk_saturn_midi_68k_r27_channel_timbre(9, 0, 35) == SATURN_MIDI_68K_R27_DRUM_KICK
    assert srk_saturn_midi_68k_r27_channel_timbre(9, 0, 40) == SATURN_MIDI_68K_R27_DRUM_SNARE
    assert srk_saturn_midi_68k_r27_channel_timbre(9, 0, 42) == SATURN_MIDI_68K_R27_DRUM_HIHAT
    assert srk_saturn_midi_68k_r27_channel_timbre(9, 0, 51) == SATURN_MIDI_68K_R27_DRUM_CYMBAL


def test_r27_program_mapping_uses_gm_eight_program_families():
    assert tuple(srk_saturn_midi_68k_r27_program_timbre(i * 8) for i in range(16)) == tuple(range(16))
    assert srk_saturn_midi_68k_r27_program_timbre(127) == 15
    assert srk_saturn_midi_68k_r27_program_timbre(30) == 3
    assert srk_saturn_midi_68k_r27_program_timbre(39) == 4
    assert srk_saturn_midi_68k_r27_program_timbre(73) == 9
    assert srk_saturn_midi_68k_r27_program_timbre(120) == 15


def test_r27_compact_source_tables_cover_all_programs_and_notes():
    programs = build_srk_saturn_midi_68k_r27_program_source_table()
    drums = build_srk_saturn_midi_68k_r27_percussion_source_table()
    assert len(programs) == len(drums) == 128
    assert programs[30] == SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS + 3 * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
    assert programs[39] == SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS + 4 * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
    assert drums[35] == SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS + SATURN_MIDI_68K_R27_DRUM_KICK * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
    assert drums[51] == SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS + SATURN_MIDI_68K_R27_DRUM_CYMBAL * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES


def test_r27_mixer_applies_volume_expression_and_pan_without_overlapping_fields():
    pan_table = build_srk_saturn_midi_68k_r27_pan_table()
    assert len(pan_table) == 128
    assert pan_table[64] == 0
    assert pan_table[0] != pan_table[127]

    center = srk_saturn_midi_68k_r27_mixer_word(
        127, volume=100, expression=127, pan=64
    )
    left = srk_saturn_midi_68k_r27_mixer_word(
        127, volume=100, expression=127, pan=0
    )
    right = srk_saturn_midi_68k_r27_mixer_word(
        127, volume=100, expression=127, pan=127
    )
    assert (center & 0x1F00) == 0
    assert (left & 0xE000) == (center & 0xE000) == (right & 0xE000)
    assert (left & 0x1F00) != (right & 0x1F00)
    assert (srk_saturn_midi_68k_r27_mixer_word(127, volume=0, expression=127, pan=64) & 0xE000) == 0
    assert (srk_saturn_midi_68k_r27_mixer_word(127, volume=127, expression=0, pan=64) & 0xE000) == 0


def test_r27_audio_data_remains_below_resident_program():
    validate_srk_saturn_midi_68k_r27_resident_audio_layout()
    assert SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS == 0x3C00
    assert SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS == 0x3D00
    assert SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS == 0x3E00
    assert SATURN_MIDI_68K_R27_AUDIO_DATA_END == 0x3F00
    assert SATURN_MIDI_68K_R27_AUDIO_DATA_END < 0x4000


def test_r27_image_is_deterministic_and_restores_r26_hooks():
    before_init = r26._emit_r26_initialization
    before_key = r26._emit_r26_key_on_slot
    first = build_srk_saturn_midi_68k_r27_resident_audio_service_image(release_rate=16)
    second = build_srk_saturn_midi_68k_r27_resident_audio_service_image(release_rate=16)
    assert first.sha256 == second.sha256
    assert first.words == second.words
    assert first.end_address <= r26.SATURN_MIDI_68K_R26_RESIDENT_AUDIO_MAX_END
    assert r26._emit_r26_initialization is before_init
    assert r26._emit_r26_key_on_slot is before_key


def test_r27_gate_patch_is_scoped_and_preserves_stream_contract():
    original_build = r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image
    original_main = r26_gate.derive_r26_double_impact_candidate_main
    with _patched_r27_gate(release_rate=16) as image:
        assert r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image is build_srk_saturn_midi_68k_r27_resident_audio_service_image
        assert r26_gate.derive_r26_double_impact_candidate_main is derive_r27_fidelity_candidate_main
        assert r26_gate.ACCEPTED_R26_IMAGE_SHA256 == image.sha256
        assert r26_gate.ACCEPTED_R26_RECORDS == 9154
        assert r26_gate.ACCEPTED_R26_BATCHES == 287
        assert r26_gate.ACCEPTED_R26_BUSY == 0
    assert r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image is original_build
    assert r26_gate.derive_r26_double_impact_candidate_main is original_main
