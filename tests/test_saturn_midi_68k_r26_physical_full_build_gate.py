from __future__ import annotations

from pathlib import Path

from rikai_kotoba.hardware.saturn.midi_68k_r26_physical_candidate_full_build_gate import (
    ACCEPTED_R26_BATCHES,
    ACCEPTED_R26_BUSY,
    ACCEPTED_R26_IMAGE_BYTES,
    ACCEPTED_R26_IMAGE_SHA256,
    ACCEPTED_R26_IMAGE_WORDS,
    ACCEPTED_R26_RECORDS,
    ACCEPTED_R26_RELEASE_STEALS,
    _validate_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_resident_audio_service import (
    build_srk_saturn_midi_68k_r26_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_voice_header import (
    render_srk_saturn_midi_68k_r26_voice_header,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_r26_full_build_gate_pins_eridu_accepted_source_engine():
    profile = _validate_profile(_ROOT)
    assert profile.record_count == ACCEPTED_R26_RECORDS == 9154
    assert profile.batch_count == ACCEPTED_R26_BATCHES == 287
    assert profile.capacity.release_steal_count == ACCEPTED_R26_RELEASE_STEALS == 12
    assert profile.capacity.busy_count == ACCEPTED_R26_BUSY == 0
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(release_rate=16)
    assert image.sha256 == ACCEPTED_R26_IMAGE_SHA256
    assert image.word_count == ACCEPTED_R26_IMAGE_WORDS == 31685
    assert image.byte_size == ACCEPTED_R26_IMAGE_BYTES == 63370


def test_r26_voice_header_exposes_16_slot_release_ledger():
    header = render_srk_saturn_midi_68k_r26_voice_header()
    assert "SRK_MIDI_68K_R26_OWNED_SLOTS 16u" in header
    assert "SRK_MIDI_68K_R26_VOICE_RELEASE_CANCELLED_WORD 15u" in header
    assert "SRK_MIDI_68K_R26_VOICE_PEAK_OWNED_WORD 12u" in header
