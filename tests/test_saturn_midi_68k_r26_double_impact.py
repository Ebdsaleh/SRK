from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_SHA256,
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
    SATURN_MIDI_68K_R26_TARGET_SLOTS,
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
    load_srk_saturn_midi_68k_r26_space_spectre_bytes,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


_ROOT = Path(__file__).resolve().parents[1]


def test_r26_space_spectre_is_exact_locked_source():
    data = load_srk_saturn_midi_68k_r26_space_spectre_bytes(_ROOT)
    assert sha256(data).hexdigest() == SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256


def test_r26_space_spectre_profiles_real_multi_channel_midi():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    assert profile.archive_sha256 == SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_SHA256
    assert profile.member_sha256 == SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
    assert profile.record_count > 100
    assert profile.duration_us > 1_000_000
    assert profile.note_on_count > 0
    assert profile.note_off_count > 0
    assert len(profile.note_channels) >= 2
    assert profile.program_change_count >= 2
    assert dict(profile.opcode_counts)[SaturnMidiOpcode.NOTE_ON] == profile.note_on_count


def test_r26_space_spectre_fits_first_16_voice_release_policy():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    assert profile.capacity.slot_capacity == SATURN_MIDI_68K_R26_TARGET_SLOTS
    assert profile.capacity.peak_owned <= SATURN_MIDI_68K_R26_TARGET_SLOTS
    assert profile.capacity.busy_count == 0
    assert profile.capacity.final_held == 0
    assert profile.capacity.final_releasing == 0
