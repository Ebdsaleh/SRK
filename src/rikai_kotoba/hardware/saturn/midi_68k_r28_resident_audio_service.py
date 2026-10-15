"""R28 percussion-first resident audio wrapper.

The complete R27 melodic/mixer path and physically accepted R26 FIX1 transport
remain unchanged. R28 changes channel-10 key-on semantics only:

* GM drum note selects the drum source but no longer doubles as melodic pitch;
* each drum uses a fixed calibrated playback-rate policy;
* LSA is moved to a zero-valued tail while LEA remains 100, turning the proven
  NORMAL_LOOP mode into a deterministic one-hit transient followed by silence;
* two unused ledger words count percussion key-ons and retain the last drum note.

Ordinary R25/R26 Note Off and release ownership still retire the voice, so the
transport/lifecycle proof remains comparable to R27.
"""

from __future__ import annotations

from . import midi_68k_resident_audio_service as _r23
from . import midi_68k_r25_resident_audio_service as _r25
from . import midi_68k_r26_resident_audio_service as _r26
from . import midi_68k_r27_resident_audio_service as _r27
from .midi_68k_r25_release_lifecycle import SaturnMidi68KR25SlotPhase
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_SLOT_CONTROL,
    SATURN_MIDI_68K_SCSP_SLOT_LEA,
    SATURN_MIDI_68K_SCSP_SLOT_LSA,
    SATURN_MIDI_68K_SCSP_SLOT_PITCH,
)
from .midi_68k_r27_fidelity_bank import (
    SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL,
    SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS,
    build_srk_saturn_midi_68k_r27_pan_table,
    build_srk_saturn_midi_68k_r27_percussion_source_table,
    build_srk_saturn_midi_68k_r27_program_source_table,
)
from .midi_68k_r28_percussion_bank import (
    SATURN_MIDI_68K_R28_AUDIO_DATA_END,
    SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_R28_DRUM_LOOP_END,
    SATURN_MIDI_68K_R28_DRUM_LOOP_START,
    SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD,
    SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS,
    build_srk_saturn_midi_68k_r28_percussion_pitch_table,
    build_srk_saturn_midi_68k_r28_timbre_bank,
    validate_srk_saturn_midi_68k_r28_percussion_layout,
)


class SaturnMidi68KR28ResidentAudioServiceError(RuntimeError):
    pass


def validate_srk_saturn_midi_68k_r28_resident_audio_layout() -> None:
    _r27.validate_srk_saturn_midi_68k_r27_resident_audio_layout()
    validate_srk_saturn_midi_68k_r28_percussion_layout()
    if (
        SATURN_MIDI_68K_R28_AUDIO_DATA_END
        != _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS
    ):
        raise SaturnMidi68KR28ResidentAudioServiceError(
            "R28 audio data must end exactly where the unchanged resident program begins"
        )


def _emit_r28_initialization(
    asm: _r23._AudioAssembler68K, *, eg1: int, eg2: int, rr: int
) -> None:
    _r26._ORIGINAL_INITIALIZATION(asm, eg1=eg1, eg2=eg2, rr=rr)

    for timbre in build_srk_saturn_midi_68k_r28_timbre_bank():
        for index, word in enumerate(timbre.words):
            asm.move_imm_absw(word, timbre.address + index * 2)

    for index, word in enumerate(build_srk_saturn_midi_68k_r27_pan_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS + index * 2)

    for index, word in enumerate(build_srk_saturn_midi_68k_r27_program_source_table()):
        asm.move_imm_absw(
            word, SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS + index * 2
        )

    for index, word in enumerate(
        build_srk_saturn_midi_68k_r27_percussion_source_table()
    ):
        asm.move_imm_absw(
            word, SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS + index * 2
        )

    for index, word in enumerate(
        build_srk_saturn_midi_68k_r28_percussion_pitch_table()
    ):
        asm.move_imm_absw(
            word, SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS + index * 2
        )

    asm.move_imm_absw(
        0, _r25._global(SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD)
    )
    asm.move_imm_absw(
        0xFFFF, _r25._global(SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD)
    )


def _emit_r28_pitch_and_loop(
    asm: _r23._AudioAssembler68K,
    slot: int,
    prefix: str,
) -> None:
    percussion = f"{prefix}_r28_pitch_percussion"
    ready = f"{prefix}_r28_pitch_ready"

    asm.cmpi_w(SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL, 1)
    asm.branch_word(0x6700, percussion)

    # Melodic path retains the R27/R24 calibrated note table and explicitly
    # restores the ordinary full-loop boundaries when a former drum slot is reused.
    asm.lea_absw_an(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_imm_to_dn(0, 2)
    asm.move_dn_d16_an(
        2, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_LSA, slot), 4
    )
    asm.move_imm_to_dn(SATURN_MIDI_68K_R28_DRUM_LOOP_END, 2)
    asm.move_dn_d16_an(
        2, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_LEA, slot), 4
    )
    asm.branch_word(0x6000, ready)

    # GM channel 10: note selects the drum source; the fixed R28 table controls
    # playback rate so note 35/40/42/51 is not treated as melodic pitch.
    asm.label(percussion)
    _r25._increment(asm, SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD)
    asm.move_dn_absw(5, _r25._global(SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD))
    asm.lea_absw_an(SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_imm_to_dn(SATURN_MIDI_68K_R28_DRUM_LOOP_START, 2)
    asm.move_dn_d16_an(
        2, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_LSA, slot), 4
    )
    asm.move_imm_to_dn(SATURN_MIDI_68K_R28_DRUM_LOOP_END, 2)
    asm.move_dn_d16_an(
        2, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_LEA, slot), 4
    )

    asm.label(ready)
    asm.move_dn_absw(
        0, _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PITCH_WORD)
    )
    asm.move_dn_d16_an(
        0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_PITCH, slot), 4
    )


def _emit_r28_key_on_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    allocation: str,
) -> None:
    _r27._emit_r27_select_source(asm, slot, prefix)

    if allocation != "free":
        _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_RETRIGGER_COUNT_WORD)
    if allocation == "releasing":
        _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_RELEASE_CANCELLED_WORD)
        _r25._decrement_nonzero(
            asm,
            _r25.SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD,
            f"{prefix}_releasing",
        )
        _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD)
    elif allocation == "free":
        _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD)
        _r25._increment(asm, _r25.SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD)

    asm.move_absw_to_dn(
        _r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD), 0
    )
    asm.addq_w(1, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, f"{prefix}_generation_ready")
    asm.move_imm_to_dn(1, 0)
    asm.label(f"{prefix}_generation_ready")
    asm.move_dn_absw(
        0, _r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD)
    )
    asm.move_dn_absw(
        0,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_GENERATION_WORD),
    )
    asm.move_imm_absw(
        int(SaturnMidi68KR25SlotPhase.HELD),
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD),
    )
    asm.move_dn_absw(
        1, _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD)
    )
    asm.move_dn_absw(
        5, _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_NOTE_WORD)
    )
    asm.move_dn_absw(
        7, _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD)
    )
    for field in (
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD,
    ):
        asm.move_imm_absw(0, _r25._slot_word(slot, field))

    _emit_r28_pitch_and_loop(asm, slot, prefix)
    _r27._emit_r27_mixer(asm, slot, prefix)

    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
        0,
    )
    asm.move_dn_absw(
        0, _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_CONTROL_WORD)
    )
    asm.move_dn_d16_an(
        0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4
    )
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONB
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(
        0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4
    )
    _r25._update_peak(
        asm,
        _r25.SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD,
        _r25.SATURN_MIDI_68K_R25_VOICE_PEAK_HELD_WORD,
        f"{prefix}_peak_held",
    )
    _r25._update_peak(
        asm,
        _r25.SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD,
        _r25.SATURN_MIDI_68K_R25_VOICE_PEAK_OWNED_WORD,
        f"{prefix}_peak_owned",
    )
    asm.move_imm_absw(
        _r25.SATURN_MIDI_68K_R25_VOICE_ERROR_NONE,
        _r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD),
    )
    asm.branch_word(0x6000, "r25_audio_note_on_done")


def build_srk_saturn_midi_68k_r28_resident_audio_service_image(*, release_rate: int):
    """Build R28 while retaining R27 melodic/mixer and FIX1 scheduler paths."""
    validate_srk_saturn_midi_68k_r28_resident_audio_layout()

    original_init = _r27._emit_r27_initialization
    original_key_on = _r27._emit_r27_key_on_slot
    try:
        _r27._emit_r27_initialization = _emit_r28_initialization
        _r27._emit_r27_key_on_slot = _emit_r28_key_on_slot
        return _r27.build_srk_saturn_midi_68k_r27_resident_audio_service_image(
            release_rate=release_rate
        )
    finally:
        _r27._emit_r27_initialization = original_init
        _r27._emit_r27_key_on_slot = original_key_on


def _render_with_r28(renderer, *, release_rate: int) -> str:
    original_build = _r27.build_srk_saturn_midi_68k_r27_resident_audio_service_image
    try:
        _r27.build_srk_saturn_midi_68k_r27_resident_audio_service_image = (
            build_srk_saturn_midi_68k_r28_resident_audio_service_image
        )
        return renderer(release_rate=release_rate)
    finally:
        _r27.build_srk_saturn_midi_68k_r27_resident_audio_service_image = original_build


def render_srk_saturn_midi_68k_r28_resident_audio_service_header(*, release_rate: int) -> str:
    return _render_with_r28(
        _r27.render_srk_saturn_midi_68k_r27_resident_audio_service_header,
        release_rate=release_rate,
    )


def render_srk_saturn_midi_68k_r28_resident_audio_service_source(*, release_rate: int) -> str:
    return _render_with_r28(
        _r27.render_srk_saturn_midi_68k_r27_resident_audio_service_source,
        release_rate=release_rate,
    )
