"""R27 fidelity-pass resident audio wrapper.

R27 keeps the physically accepted R26 FIX1 scheduler/transport byte path and
changes only source selection plus Note-On mixing. The 68K still consumes the
same SRKM stream, owns the same sixteen voices and uses the same RR16 release
policy.

Fidelity pass 1 adds:
* 16 GM eight-program source families;
* distinct kick/snare/hi-hat/cymbal sources for Space Spectre channel 10;
* channel Volume and Expression attenuation at Note On;
* channel Pan in the SCSP direct-output mixer word.

Active-voice pitch bend remains deliberately deferred.
"""

from __future__ import annotations

from . import midi_68k_resident_audio_service as _r23
from . import midi_68k_r25_resident_audio_service as _r25
from . import midi_68k_r26_resident_audio_service as _r26
from . import midi_68k_r26_fix1_resident_audio_service as _fix1
from .midi_68k_command_engine import (
    SATURN_MIDI_68K_CH_EXPRESSION,
    SATURN_MIDI_68K_CH_PAN,
    SATURN_MIDI_68K_CH_PROGRAM,
    SATURN_MIDI_68K_CH_VOLUME,
)
from .midi_68k_r25_release_lifecycle import SaturnMidi68KR25SlotPhase
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_SLOT_CONTROL,
    SATURN_MIDI_68K_SCSP_SLOT_MIXER,
    SATURN_MIDI_68K_SCSP_SLOT_PITCH,
    SATURN_MIDI_68K_SCSP_SLOT_SA_LOW,
)
from .midi_68k_r27_fidelity_bank import (
    SATURN_MIDI_68K_R27_AUDIO_DATA_END,
    SATURN_MIDI_68K_R27_GM_FAMILY_COUNT,
    SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL,
    SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS,
    SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS,
    SATURN_MIDI_68K_R27_TIMBRE_COUNT,
    SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES,
    build_srk_saturn_midi_68k_r27_pan_table,
    build_srk_saturn_midi_68k_r27_percussion_source_table,
    build_srk_saturn_midi_68k_r27_program_source_table,
    build_srk_saturn_midi_68k_r27_timbre_bank,
)


class SaturnMidi68KR27ResidentAudioServiceError(RuntimeError):
    pass


def validate_srk_saturn_midi_68k_r27_resident_audio_layout() -> None:
    _fix1.validate_srk_saturn_midi_68k_r26_fix1_layout()
    if SATURN_MIDI_68K_R27_GM_FAMILY_COUNT != 16:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 must expose 16 GM families")
    if SATURN_MIDI_68K_R27_TIMBRE_COUNT != 20:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 timbre count changed")
    if SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS != _r26.SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 timbre bank base changed")
    expected_pan = (
        SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS
        + SATURN_MIDI_68K_R27_TIMBRE_COUNT * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
    )
    if SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS != expected_pan:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 pan table is not packed after timbres")
    if SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS != SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS + 0x100:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 program table boundary changed")
    if SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS != SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS + 0x100:
        raise SaturnMidi68KR27ResidentAudioServiceError("R27 percussion table boundary changed")
    if SATURN_MIDI_68K_R27_AUDIO_DATA_END > _r25.SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS:
        raise SaturnMidi68KR27ResidentAudioServiceError(
            "R27 fidelity data overlaps the resident program"
        )


def _emit_r27_initialization(
    asm: _r23._AudioAssembler68K, *, eg1: int, eg2: int, rr: int
) -> None:
    _r26._ORIGINAL_INITIALIZATION(asm, eg1=eg1, eg2=eg2, rr=rr)
    for timbre in build_srk_saturn_midi_68k_r27_timbre_bank():
        for index, word in enumerate(timbre.words):
            asm.move_imm_absw(word, timbre.address + index * 2)
    for index, word in enumerate(build_srk_saturn_midi_68k_r27_pan_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS + index * 2)
    for index, word in enumerate(build_srk_saturn_midi_68k_r27_program_source_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS + index * 2)
    for index, word in enumerate(build_srk_saturn_midi_68k_r27_percussion_source_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS + index * 2)


def _emit_r27_select_source(
    asm: _r23._AudioAssembler68K, slot: int, prefix: str
) -> None:
    """Select a source through compact 128-entry address tables."""
    percussion = f"{prefix}_r27_percussion"
    lookup = f"{prefix}_r27_source_lookup"

    asm.cmpi_w(SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL, 1)
    asm.branch_word(0x6700, percussion)

    asm.lea_absw_an(SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS, 5)
    asm.move_d16_an_to_dn(
        1,
        _r23._state_displacement(SATURN_MIDI_68K_CH_PROGRAM),
        0,
    )
    asm.branch_word(0x6000, lookup)

    asm.label(percussion)
    asm.lea_absw_an(SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)

    asm.label(lookup)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_SA_LOW, slot),
        4,
    )


def _emit_level_lookup(
    asm: _r23._AudioAssembler68K,
    source_register: int,
    destination_register: int,
) -> None:
    asm.lea_absw_an(_r26.SATURN_MIDI_68K_R26_MIXER_TABLE_ADDRESS, 5)
    if source_register != destination_register:
        asm.move_dn_to_dn(source_register, destination_register)
    asm.add_w_dn_to_dn(destination_register, destination_register)
    asm.adda_w_dn_an(destination_register, 5)
    asm.move_d16_an_to_dn(5, 0, destination_register)
    asm.andi_w(0xE000, destination_register)


def _emit_min_level(
    asm: _r23._AudioAssembler68K,
    current_register: int,
    candidate_register: int,
    label: str,
) -> None:
    asm.cmp_dn_w(candidate_register, current_register)
    asm.branch_word(0x6300, label)
    asm.move_dn_to_dn(candidate_register, current_register)
    asm.label(label)


def _emit_r27_mixer(
    asm: _r23._AudioAssembler68K,
    slot: int,
    prefix: str,
) -> None:
    _emit_level_lookup(asm, 7, 0)

    asm.move_d16_an_to_dn(
        1,
        _r23._state_displacement(SATURN_MIDI_68K_CH_VOLUME),
        2,
    )
    _emit_level_lookup(asm, 2, 2)
    _emit_min_level(asm, 0, 2, f"{prefix}_r27_volume_min_done")

    asm.move_d16_an_to_dn(
        1,
        _r23._state_displacement(SATURN_MIDI_68K_CH_EXPRESSION),
        2,
    )
    _emit_level_lookup(asm, 2, 2)
    _emit_min_level(asm, 0, 2, f"{prefix}_r27_expression_min_done")

    asm.lea_absw_an(SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS, 5)
    asm.move_d16_an_to_dn(
        1,
        _r23._state_displacement(SATURN_MIDI_68K_CH_PAN),
        2,
    )
    asm.add_w_dn_to_dn(2, 2)
    asm.adda_w_dn_an(2, 5)
    asm.move_d16_an_to_dn(5, 0, 2)
    asm.add_w_dn_to_dn(2, 0)

    asm.move_dn_absw(
        0,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_MIXER_WORD),
    )
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER, slot),
        4,
    )


def _emit_r27_key_on_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    allocation: str,
) -> None:
    _emit_r27_select_source(asm, slot, prefix)

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

    asm.move_absw_to_dn(_r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD), 0)
    asm.addq_w(1, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, f"{prefix}_generation_ready")
    asm.move_imm_to_dn(1, 0)
    asm.label(f"{prefix}_generation_ready")
    asm.move_dn_absw(0, _r25._global(_r25.SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD))
    asm.move_dn_absw(
        0,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_GENERATION_WORD),
    )
    asm.move_imm_absw(
        int(SaturnMidi68KR25SlotPhase.HELD),
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PHASE_WORD),
    )
    asm.move_dn_absw(
        1,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD),
    )
    asm.move_dn_absw(
        5,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_NOTE_WORD),
    )
    asm.move_dn_absw(
        7,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD),
    )
    for field in (
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD,
        _r25.SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD,
    ):
        asm.move_imm_absw(0, _r25._slot_word(slot, field))

    asm.lea_absw_an(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(
        0,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_PITCH_WORD),
    )
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_PITCH, slot),
        4,
    )

    _emit_r27_mixer(asm, slot, prefix)

    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
        0,
    )
    asm.move_dn_absw(
        0,
        _r25._slot_word(slot, _r25.SATURN_MIDI_68K_R25_SLOT_CONTROL_WORD),
    )
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot),
        4,
    )
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONB
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(
        0,
        _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot),
        4,
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


def build_srk_saturn_midi_68k_r27_resident_audio_service_image(*, release_rate: int):
    """Build R27 on top of the physically accepted FIX1 scheduler."""
    validate_srk_saturn_midi_68k_r27_resident_audio_layout()
    original_init = _r26._emit_r26_initialization
    original_key_on = _r26._emit_r26_key_on_slot
    try:
        _r26._emit_r26_initialization = _emit_r27_initialization
        _r26._emit_r26_key_on_slot = _emit_r27_key_on_slot
        return _fix1.build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(
            release_rate=release_rate
        )
    finally:
        _r26._emit_r26_initialization = original_init
        _r26._emit_r26_key_on_slot = original_key_on


def _render_with_r27(renderer, *, release_rate: int) -> str:
    original_build = _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image
    try:
        _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image = (
            build_srk_saturn_midi_68k_r27_resident_audio_service_image
        )
        return renderer(release_rate=release_rate)
    finally:
        _r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image = original_build


def render_srk_saturn_midi_68k_r27_resident_audio_service_header(*, release_rate: int) -> str:
    return _render_with_r27(
        _r26.render_srk_saturn_midi_68k_r26_resident_audio_service_header,
        release_rate=release_rate,
    )


def render_srk_saturn_midi_68k_r27_resident_audio_service_source(*, release_rate: int) -> str:
    return _render_with_r27(
        _r26.render_srk_saturn_midi_68k_r26_resident_audio_service_source,
        release_rate=release_rate,
    )
