from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r25_resident_audio_service as r25
from rikai_kotoba.hardware.saturn.midi_68k_r26_resident_audio_service import (
    SATURN_MIDI_68K_R26_OWNED_SLOTS,
    build_srk_saturn_midi_68k_r26_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_timbre_bank import (
    SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE,
    SATURN_MIDI_68K_R26_TIMBRE_COUNT,
    build_srk_saturn_midi_68k_r26_timbre_bank,
    srk_saturn_midi_68k_r26_channel_timbre,
    srk_saturn_midi_68k_r26_program_timbre,
)


def test_r26_timbre_bank_is_nine_distinct_bounded_loops():
    bank = build_srk_saturn_midi_68k_r26_timbre_bank()
    assert len(bank) == SATURN_MIDI_68K_R26_TIMBRE_COUNT == 9
    assert len({timbre.words for timbre in bank}) == 9
    assert all(len(timbre.words) == 101 for timbre in bank)
    assert all(timbre.words[0] == timbre.words[-1] for timbre in bank)


def test_r26_program_families_and_percussion_are_deterministic():
    assert tuple(srk_saturn_midi_68k_r26_program_timbre(i * 16) for i in range(8)) == tuple(range(8))
    assert srk_saturn_midi_68k_r26_program_timbre(127) == 7
    assert srk_saturn_midi_68k_r26_channel_timbre(9, 0) == SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE
    assert srk_saturn_midi_68k_r26_channel_timbre(0, 32) == 2


def test_r26_resident_image_build_is_scoped_and_restores_r25_globals():
    before = (
        r25.SATURN_MIDI_68K_R25_OWNED_SLOTS,
        r25.SATURN_MIDI_68K_R25_VOICE_STATE_BYTES,
        r25.SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS,
        r25.SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END,
        r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END,
        r25.validate_saturn_midi_68k_r25_resident_audio_layout,
        r25._emit_r25_initialization,
        r25._emit_r25_key_on_slot,
    )
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(release_rate=16)
    after = (
        r25.SATURN_MIDI_68K_R25_OWNED_SLOTS,
        r25.SATURN_MIDI_68K_R25_VOICE_STATE_BYTES,
        r25.SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS,
        r25.SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END,
        r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END,
        r25.validate_saturn_midi_68k_r25_resident_audio_layout,
        r25._emit_r25_initialization,
        r25._emit_r25_key_on_slot,
    )
    assert before == after
    assert SATURN_MIDI_68K_R26_OWNED_SLOTS == 16
    assert image.release_rate == 16
    assert image.word_count > 0
    assert image.byte_size == image.word_count * 2
