"""R26 FIX1 resident-service repair for the physical Space Spectre failure.

The first physical R26 run reached real MC68EC000/SCSP playback, processed 17
records, then stopped with stream error 7 (invalid record).  The whole first
batch had already passed resident validation, so the failure occurred while
applying a previously accepted record.

Root cause: the R25-derived timestamp wait hook calls ``_emit_retire_expired``
while D4 still owns the current record's MIDI channel.  The retirement helper
uses D4 as scratch.  When the record finally becomes due, channel dispatch sees
the scratch value rather than the channel and takes ``error_record``.

FIX1 is deliberately R26-only.  It stores D4 in one previously unused global
word in the enlarged R26 voice ledger before entering the wait loop and restores
D4 once the timestamp is due.  R24 and R25 generation remain byte-identical.
"""

from __future__ import annotations

from . import midi_68k_resident_audio_service as _r23
from . import midi_68k_r25_resident_audio_service as _r25
from . import midi_68k_r26_resident_audio_service as _r26
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_RUNNING,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET,
)


SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD = 23
SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS = (
    _r26.SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS
    + SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD * 2
)

_ORIGINAL_R26_BUILD = _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image


class SaturnMidi68KR26Fix1Error(RuntimeError):
    """Raised if the FIX1 register-preservation contract cannot be generated."""


def validate_srk_saturn_midi_68k_r26_fix1_layout() -> None:
    _r26.validate_srk_saturn_midi_68k_r26_resident_audio_layout()
    if (
        SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD
        >= _r25.SATURN_MIDI_68K_R25_SLOT_BASE_WORD
    ):
        raise SaturnMidi68KR26Fix1Error(
            "FIX1 wait-channel scratch overlaps the first R26 voice slot"
        )
    if SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD <= _r25.SATURN_MIDI_68K_R25_VOICE_RELEASE_US_LO_WORD:
        raise SaturnMidi68KR26Fix1Error(
            "FIX1 wait-channel scratch overlaps an R25 global voice word"
        )
    end = SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS + 2
    if end > _r26.SATURN_MIDI_68K_R26_VOICE_STATE_ADDRESS + _r26.SATURN_MIDI_68K_R26_VOICE_STATE_BYTES:
        raise SaturnMidi68KR26Fix1Error("FIX1 scratch escapes the R26 voice ledger")


def _emit_r26_fix1_wait_until_due(asm) -> None:
    """R25 due-time wait with the live record channel D4 preserved exactly."""

    # D4 is the current record's MIDI channel until _emit_channel_dispatch runs.
    # R25's release retirement helper uses D4 as scratch, so save it once before
    # entering the potentially repeated scheduler wait loop.
    asm.move_dn_absw(4, SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS)

    asm.move_dn_absw(2, _r23._svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET))
    asm.move_dn_absw(3, _r23._svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET))
    asm.move_imm_absw(
        SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
        _r23._svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET),
    )
    asm.label("scheduler_wait")
    _r25._emit_prefixed_clock_read(asm, "r25_wait")
    _r25._emit_retire_expired(asm, "r25_wait")
    asm.move_absw_to_dn(
        _r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET), 0
    )
    asm.move_absw_to_dn(
        _r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET), 1
    )
    asm.cmp_dn_w(2, 0)
    asm.branch_word(0x6500, "scheduler_wait")
    asm.branch_word(0x6200, "scheduler_due")
    asm.cmp_dn_w(3, 1)
    asm.branch_word(0x6500, "scheduler_wait")
    asm.label("scheduler_due")

    # Restore the validated record channel immediately before dispatch.  R23's
    # dispatch then copies this restored D4 into D1 for voice-owner semantics.
    asm.move_absw_to_dn(SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS, 4)
    asm.move_imm_absw(
        SATURN_MIDI_68K_STREAM_FLAG_RUNNING,
        _r23._svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET),
    )


def build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(*, release_rate: int):
    """Build the R26 image with only the D4 wait-loop lifetime repair applied."""

    validate_srk_saturn_midi_68k_r26_fix1_layout()
    original_wait = _r25._emit_r25_wait_until_due
    try:
        _r25._emit_r25_wait_until_due = _emit_r26_fix1_wait_until_due
        return _ORIGINAL_R26_BUILD(release_rate=release_rate)
    finally:
        _r25._emit_r25_wait_until_due = original_wait


def _render_with_fix1(renderer, *, release_rate: int) -> str:
    original_build = _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image
    try:
        _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image = (
            build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image
        )
        return renderer(release_rate=release_rate)
    finally:
        _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image = original_build


def render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_header(*, release_rate: int) -> str:
    return _render_with_fix1(
        _r26.render_srk_saturn_midi_68k_r26_resident_audio_service_header,
        release_rate=release_rate,
    )


def render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_source(*, release_rate: int) -> str:
    return _render_with_fix1(
        _r26.render_srk_saturn_midi_68k_r26_resident_audio_service_source,
        release_rate=release_rate,
    )
