"""R25 four-slot MC68EC000 MIDI -> SCSP release-tail service.

The service is derived from the physically accepted R23 stream engine through
its audio callbacks.  R25 owns four slots, programs an explicit SCSP RR value,
keeps Note Off mixer level intact during the envelope release, and retires a
slot only after the reviewed 120-ms lifecycle deadline.

``release_rate`` is deliberately required.  Generating all 32 inert variants
is safe, but choosing one physical policy remains the calibration gate's job.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from . import midi_68k_resident_audio_service as _r23
from .midi_68k_r24_pitch import build_saturn_midi_68k_r24_pitch_table
from .midi_68k_r24_resident_audio_service import build_saturn_midi_68k_r24_mixer_table
from .midi_68k_r25_envelope import build_saturn_midi_68k_r25_envelope_plan
from .midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
)
from .midi_68k_r25_release_lifecycle import SaturnMidi68KR25SlotPhase
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_RUNNING,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET,
)
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END,
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_SCSP_COMMON_ADDRESS,
    SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_SCSP_SLOT_CONTROL,
    SATURN_MIDI_68K_SCSP_SLOT_COUNT,
    SATURN_MIDI_68K_SCSP_SLOT_DSP,
    SATURN_MIDI_68K_SCSP_SLOT_EG1,
    SATURN_MIDI_68K_SCSP_SLOT_EG2,
    SATURN_MIDI_68K_SCSP_SLOT_FM,
    SATURN_MIDI_68K_SCSP_SLOT_LEA,
    SATURN_MIDI_68K_SCSP_SLOT_LFO,
    SATURN_MIDI_68K_SCSP_SLOT_LSA,
    SATURN_MIDI_68K_SCSP_SLOT_MIXER,
    SATURN_MIDI_68K_SCSP_SLOT_PITCH,
    SATURN_MIDI_68K_SCSP_SLOT_SA_LOW,
    SATURN_MIDI_68K_SCSP_SLOT_TL,
    SATURN_MIDI_68K_SCSP_SOUND_DIRECT,
)


SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS = 0x00004000
SATURN_MIDI_68K_R25_RESIDENT_AUDIO_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END = 0x0000A000
SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_RECORDS = 32

SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS = 0x00002300
SATURN_MIDI_68K_R25_VOICE_STATE_BYTES = 0x00000100
SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS = 0x00002400
SATURN_MIDI_68K_R25_MIXER_TABLE_BYTES = 0x00000100
SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END = 0x00002500

SATURN_MIDI_68K_R25_VOICE_MAGIC = 0x5634  # "V4"
SATURN_MIDI_68K_R25_VOICE_VERSION = 1
SATURN_MIDI_68K_R25_VOICE_ERROR_NONE = 0
SATURN_MIDI_68K_R25_VOICE_ERROR_BUSY = 1

# Global words in the 0x2300 voice ledger.
SATURN_MIDI_68K_R25_VOICE_MAGIC_WORD = 0
SATURN_MIDI_68K_R25_VOICE_VERSION_WORD = 1
SATURN_MIDI_68K_R25_VOICE_OWNED_SLOTS_WORD = 2
SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD = 3
SATURN_MIDI_68K_R25_VOICE_KEY_ON_COUNT_WORD = 4
SATURN_MIDI_68K_R25_VOICE_KEY_OFF_COUNT_WORD = 5
SATURN_MIDI_68K_R25_VOICE_BUSY_COUNT_WORD = 6
SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD = 7
SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD = 8
SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD = 9
SATURN_MIDI_68K_R25_VOICE_PEAK_HELD_WORD = 10
SATURN_MIDI_68K_R25_VOICE_PEAK_RELEASING_WORD = 11
SATURN_MIDI_68K_R25_VOICE_PEAK_OWNED_WORD = 12
SATURN_MIDI_68K_R25_VOICE_RELEASE_STARTED_WORD = 13
SATURN_MIDI_68K_R25_VOICE_RELEASE_COMPLETED_WORD = 14
SATURN_MIDI_68K_R25_VOICE_RELEASE_CANCELLED_WORD = 15
SATURN_MIDI_68K_R25_VOICE_RETRIGGER_COUNT_WORD = 16
SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD = 17
SATURN_MIDI_68K_R25_VOICE_RR_WORD = 18
SATURN_MIDI_68K_R25_VOICE_EG1_WORD = 19
SATURN_MIDI_68K_R25_VOICE_EG2_WORD = 20
SATURN_MIDI_68K_R25_VOICE_RELEASE_US_HI_WORD = 21
SATURN_MIDI_68K_R25_VOICE_RELEASE_US_LO_WORD = 22

# Twelve words per slot, starting at word 32.
SATURN_MIDI_68K_R25_SLOT_BASE_WORD = 32
SATURN_MIDI_68K_R25_SLOT_WORDS = 12
SATURN_MIDI_68K_R25_SLOT_PHASE_WORD = 0
SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD = 1
SATURN_MIDI_68K_R25_SLOT_NOTE_WORD = 2
SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD = 3
SATURN_MIDI_68K_R25_SLOT_GENERATION_WORD = 4
SATURN_MIDI_68K_R25_SLOT_PITCH_WORD = 5
SATURN_MIDI_68K_R25_SLOT_MIXER_WORD = 6
SATURN_MIDI_68K_R25_SLOT_CONTROL_WORD = 7
SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD = 8
SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD = 9
SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD = 10
SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD = 11


class SaturnMidi68KR25ResidentAudioServiceError(RuntimeError):
    """Raised when the R25 resident service cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KR25ResidentAudioServiceImage:
    release_rate: int
    eg1_word: int
    eg2_word: int
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return self.word_count * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


def _global(word_index: int) -> int:
    return SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS + word_index * 2


def _slot_word(slot: int, field: int) -> int:
    if slot < 0 or slot >= SATURN_MIDI_68K_R25_OWNED_SLOTS:
        raise SaturnMidi68KR25ResidentAudioServiceError("R25 slot escapes owned range")
    if field < 0 or field >= SATURN_MIDI_68K_R25_SLOT_WORDS:
        raise SaturnMidi68KR25ResidentAudioServiceError("R25 slot field escapes ledger")
    index = SATURN_MIDI_68K_R25_SLOT_BASE_WORD + slot * SATURN_MIDI_68K_R25_SLOT_WORDS + field
    return SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS + index * 2


def validate_saturn_midi_68k_r25_resident_audio_layout() -> None:
    if SATURN_MIDI_68K_R25_OWNED_SLOTS != 4:
        raise SaturnMidi68KR25ResidentAudioServiceError("R25 must own exactly four slots")
    if SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + 0x100 != SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS:
        raise SaturnMidi68KR25ResidentAudioServiceError("pitch/voice boundary changed")
    if SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS + SATURN_MIDI_68K_R25_VOICE_STATE_BYTES != SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS:
        raise SaturnMidi68KR25ResidentAudioServiceError("voice/mixer boundary changed")
    if SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS + SATURN_MIDI_68K_R25_MIXER_TABLE_BYTES != SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END:
        raise SaturnMidi68KR25ResidentAudioServiceError("mixer ownership boundary changed")
    final_slot_word = SATURN_MIDI_68K_R25_SLOT_BASE_WORD + SATURN_MIDI_68K_R25_OWNED_SLOTS * SATURN_MIDI_68K_R25_SLOT_WORDS
    if final_slot_word * 2 > SATURN_MIDI_68K_R25_VOICE_STATE_BYTES:
        raise SaturnMidi68KR25ResidentAudioServiceError("four-slot ledger exceeds state block")


def _increment(asm: _r23._AudioAssembler68K, word: int) -> None:
    asm.move_absw_to_dn(_global(word), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _global(word))


def _decrement_nonzero(asm: _r23._AudioAssembler68K, word: int, prefix: str) -> None:
    asm.move_absw_to_dn(_global(word), 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, f"{prefix}_zero")
    asm.subq_w(1, 0)
    asm.move_dn_absw(0, _global(word))
    asm.label(f"{prefix}_zero")


def _update_peak(
    asm: _r23._AudioAssembler68K,
    current_word: int,
    peak_word: int,
    prefix: str,
) -> None:
    asm.move_absw_to_dn(_global(current_word), 0)
    asm.move_absw_to_dn(_global(peak_word), 4)
    asm.cmp_dn_w(4, 0)
    asm.branch_word(0x6300, f"{prefix}_done")  # BLS: current <= peak
    asm.move_dn_absw(0, _global(peak_word))
    asm.label(f"{prefix}_done")


def _emit_prefixed_clock_read(asm: _r23._AudioAssembler68K, prefix: str) -> None:
    retry = f"{prefix}_clock_retry"
    asm.label(retry)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET), 0)
    asm.move_dn_absw(0, _r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET))
    asm.andi_w(1, 0)
    asm.branch_word(0x6600, retry)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET), 0)
    asm.move_dn_absw(0, _r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET))
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET), 0)
    asm.move_dn_absw(0, _r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET))
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET), 0)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET), 1)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6600, retry)
    asm.andi_w(1, 0)
    asm.branch_word(0x6600, retry)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET), 0)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET), 1)


def _emit_retire_expired(asm: _r23._AudioAssembler68K, prefix: str) -> None:
    """Retire due release slots using the stable clock snapshot in service RAM."""

    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        next_label = f"{prefix}_retire_next_{slot}"
        due_label = f"{prefix}_retire_due_{slot}"
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0)
        asm.cmpi_w(int(SaturnMidi68KR25SlotPhase.RELEASING), 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET), 0)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD), 4)
        asm.cmp_dn_w(4, 0)
        asm.branch_word(0x6500, next_label)  # BCS: now high < deadline high
        asm.branch_word(0x6200, due_label)   # BHI: now high > deadline high
        asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET), 0)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD), 4)
        asm.cmp_dn_w(4, 0)
        asm.branch_word(0x6500, next_label)
        asm.label(due_label)
        asm.move_imm_to_dn(0, 0)
        asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER, slot), 4)
        for field, value in (
            (SATURN_MIDI_68K_R25_SLOT_PHASE_WORD, int(SaturnMidi68KR25SlotPhase.FREE)),
            (SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD, 0xFFFF),
            (SATURN_MIDI_68K_R25_SLOT_NOTE_WORD, 0xFFFF),
            (SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD, 0),
            (SATURN_MIDI_68K_R25_SLOT_MIXER_WORD, 0),
            (SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD, 0),
            (SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD, 0),
            (SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD, 0),
            (SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD, 0),
        ):
            asm.move_imm_absw(value, _slot_word(slot, field))
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_RELEASE_COMPLETED_WORD)
        _decrement_nonzero(asm, SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD, f"{prefix}_{slot}_releasing")
        _decrement_nonzero(asm, SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD, f"{prefix}_{slot}_owned")
        asm.label(next_label)


def _emit_r25_initialization(asm: _r23._AudioAssembler68K, *, eg1: int, eg2: int, rr: int) -> None:
    validate_saturn_midi_68k_r25_resident_audio_layout()
    for index, word in enumerate(_r23.build_srk_saturn_midi_68k_r23_waveform_words()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS + index * 2)
    for index, word in enumerate(build_saturn_midi_68k_r24_pitch_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + index * 2)
    for index, word in enumerate(build_saturn_midi_68k_r24_mixer_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS + index * 2)

    initial = {
        SATURN_MIDI_68K_R25_VOICE_MAGIC_WORD: SATURN_MIDI_68K_R25_VOICE_MAGIC,
        SATURN_MIDI_68K_R25_VOICE_VERSION_WORD: SATURN_MIDI_68K_R25_VOICE_VERSION,
        SATURN_MIDI_68K_R25_VOICE_OWNED_SLOTS_WORD: SATURN_MIDI_68K_R25_OWNED_SLOTS,
        SATURN_MIDI_68K_R25_VOICE_RR_WORD: rr,
        SATURN_MIDI_68K_R25_VOICE_EG1_WORD: eg1,
        SATURN_MIDI_68K_R25_VOICE_EG2_WORD: eg2,
        SATURN_MIDI_68K_R25_VOICE_RELEASE_US_HI_WORD: (SATURN_MIDI_68K_R25_TARGET_RELEASE_US >> 16) & 0xFFFF,
        SATURN_MIDI_68K_R25_VOICE_RELEASE_US_LO_WORD: SATURN_MIDI_68K_R25_TARGET_RELEASE_US & 0xFFFF,
    }
    for word in range(SATURN_MIDI_68K_R25_VOICE_RELEASE_US_LO_WORD + 1):
        asm.move_imm_absw(initial.get(word, 0), _global(word))

    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        values = (
            int(SaturnMidi68KR25SlotPhase.FREE), 0xFFFF, 0xFFFF, 0, 0, 0, 0,
            SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, 0, 0, 0, 0,
        )
        for field, value in enumerate(values):
            asm.move_imm_absw(value, _slot_word(slot, field))

    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_REGISTER_BASE, 4)
    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_COMMON_ADDRESS, 5)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE, 0)
    asm.move_dn_d16_an(0, 0, 5)
    for slot in range(SATURN_MIDI_68K_SCSP_SLOT_COUNT):
        offset = _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot)
        asm.move_d16_an_to_dn(4, offset, 0)
        asm.andi_w(0xFFFF ^ SATURN_MIDI_68K_SCSP_CONTROL_KYONB, 0)
        asm.move_dn_d16_an(0, offset, 4)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX, 0)
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, 0), 4)

    slot_values = (
        (SATURN_MIDI_68K_SCSP_SLOT_CONTROL, SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP),
        (SATURN_MIDI_68K_SCSP_SLOT_SA_LOW, SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS),
        (SATURN_MIDI_68K_SCSP_SLOT_LSA, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_LEA, SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END),
        (SATURN_MIDI_68K_SCSP_SLOT_EG1, eg1),
        (SATURN_MIDI_68K_SCSP_SLOT_EG2, eg2),
        (SATURN_MIDI_68K_SCSP_SLOT_TL, SATURN_MIDI_68K_SCSP_SOUND_DIRECT),
        (SATURN_MIDI_68K_SCSP_SLOT_FM, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_PITCH, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_LFO, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_DSP, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_MIXER, 0),
    )
    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        for register, value in slot_values:
            asm.move_imm_to_dn(value, 0)
            asm.move_dn_d16_an(0, _r23._slot_byte_offset(register, slot), 4)


def _emit_r25_key_on_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    allocation: str,
) -> None:
    if allocation != "free":
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_RETRIGGER_COUNT_WORD)
    if allocation == "releasing":
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_RELEASE_CANCELLED_WORD)
        _decrement_nonzero(asm, SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD, f"{prefix}_releasing")
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD)
    elif allocation == "free":
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD)
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD)

    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD), 0)
    asm.addq_w(1, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, f"{prefix}_generation_ready")
    asm.move_imm_to_dn(1, 0)
    asm.label(f"{prefix}_generation_ready")
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R25_VOICE_GENERATION_WORD))
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_GENERATION_WORD))
    asm.move_imm_absw(int(SaturnMidi68KR25SlotPhase.HELD), _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD))
    asm.move_dn_absw(1, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD))
    asm.move_dn_absw(5, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_NOTE_WORD))
    asm.move_dn_absw(7, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD))
    for field in (
        SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD,
        SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD,
        SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD,
        SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD,
    ):
        asm.move_imm_absw(0, _slot_word(slot, field))

    asm.lea_absw_an(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PITCH_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_PITCH, slot), 4)
    asm.lea_absw_an(SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(7, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_MIXER_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER, slot), 4)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB, 0)
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_CONTROL_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX, 0)
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
    _update_peak(asm, SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD, SATURN_MIDI_68K_R25_VOICE_PEAK_HELD_WORD, f"{prefix}_peak_held")
    _update_peak(asm, SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD, SATURN_MIDI_68K_R25_VOICE_PEAK_OWNED_WORD, f"{prefix}_peak_owned")
    asm.move_imm_absw(SATURN_MIDI_68K_R25_VOICE_ERROR_NONE, _global(SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD))
    asm.branch_word(0x6000, "r25_audio_note_on_done")


def _emit_r25_note_on(asm: _r23._AudioAssembler68K) -> None:
    _increment(asm, SATURN_MIDI_68K_R25_VOICE_KEY_ON_COUNT_WORD)
    # The scheduler has already published its stable due-time clock sample.
    _emit_retire_expired(asm, "r25_note_on")
    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        next_label = f"r25_note_on_match_next_{slot}"
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0)
        asm.cmpi_w(int(SaturnMidi68KR25SlotPhase.FREE), 0)
        asm.branch_word(0x6700, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD), 0)
        asm.cmp_dn_w(1, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_NOTE_WORD), 0)
        asm.cmp_dn_w(5, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0)
        asm.cmpi_w(int(SaturnMidi68KR25SlotPhase.RELEASING), 0)
        asm.branch_word(0x6700, f"r25_note_on_slot_{slot}_releasing")
        asm.branch_word(0x6000, f"r25_note_on_slot_{slot}_held")
        asm.label(next_label)
    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0)
        asm.cmpi_w(int(SaturnMidi68KR25SlotPhase.FREE), 0)
        asm.branch_word(0x6700, f"r25_note_on_slot_{slot}_free")
    _increment(asm, SATURN_MIDI_68K_R25_VOICE_BUSY_COUNT_WORD)
    asm.move_imm_absw(SATURN_MIDI_68K_R25_VOICE_ERROR_BUSY, _global(SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD))
    asm.branch_word(0x6000, "r25_audio_note_on_done")
    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        for allocation in ("releasing", "held", "free"):
            prefix = f"r25_note_on_slot_{slot}_{allocation}"
            asm.label(prefix)
            _emit_r25_key_on_slot(asm, slot, prefix=prefix, allocation=allocation)
    asm.label("r25_audio_note_on_done")


def _emit_r25_note_off(asm: _r23._AudioAssembler68K, prefix: str) -> None:
    _increment(asm, SATURN_MIDI_68K_R25_VOICE_KEY_OFF_COUNT_WORD)
    _emit_retire_expired(asm, f"{prefix}_retire")
    done = f"{prefix}_r25_done"
    for slot in range(SATURN_MIDI_68K_R25_OWNED_SLOTS):
        next_label = f"{prefix}_r25_next_{slot}"
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD), 0)
        asm.cmpi_w(int(SaturnMidi68KR25SlotPhase.HELD), 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_CHANNEL_WORD), 0)
        asm.cmp_dn_w(1, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R25_SLOT_NOTE_WORD), 0)
        asm.cmp_dn_w(5, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, 0)
        asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
        asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX, 0)
        asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
        asm.move_imm_absw(int(SaturnMidi68KR25SlotPhase.RELEASING), _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD))
        asm.move_imm_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_VELOCITY_WORD))
        asm.move_imm_absw(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_CONTROL_WORD))
        asm.move_dn_absw(2, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD))
        asm.move_dn_absw(3, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD))
        asm.move_dn_to_dn(3, 0)
        asm.addi_w(SATURN_MIDI_68K_R25_TARGET_RELEASE_US & 0xFFFF, 0)
        asm.branch_word(0x6400, f"{prefix}_slot_{slot}_deadline_no_carry")
        asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD))
        asm.move_dn_to_dn(2, 0)
        asm.addi_w((SATURN_MIDI_68K_R25_TARGET_RELEASE_US >> 16) + 1, 0)
        asm.branch_word(0x6000, f"{prefix}_slot_{slot}_deadline_store_hi")
        asm.label(f"{prefix}_slot_{slot}_deadline_no_carry")
        asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD))
        asm.move_dn_to_dn(2, 0)
        asm.addi_w(SATURN_MIDI_68K_R25_TARGET_RELEASE_US >> 16, 0)
        asm.label(f"{prefix}_slot_{slot}_deadline_store_hi")
        asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD))
        _decrement_nonzero(asm, SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD, f"{prefix}_{slot}_held")
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD)
        _increment(asm, SATURN_MIDI_68K_R25_VOICE_RELEASE_STARTED_WORD)
        _update_peak(asm, SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD, SATURN_MIDI_68K_R25_VOICE_PEAK_RELEASING_WORD, f"{prefix}_{slot}_peak_releasing")
        asm.move_imm_absw(SATURN_MIDI_68K_R25_VOICE_ERROR_NONE, _global(SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD))
        asm.branch_word(0x6000, done)
        asm.label(next_label)
    asm.label(done)


def _emit_r25_idle(asm: _r23._AudioAssembler68K) -> None:
    _emit_prefixed_clock_read(asm, "r25_idle")
    _emit_retire_expired(asm, "r25_idle")


def _emit_r25_wait_until_due(asm: _r23._AudioAssembler68K) -> None:
    asm.move_dn_absw(2, _r23._svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET))
    asm.move_dn_absw(3, _r23._svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET))
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME, _r23._svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
    asm.label("scheduler_wait")
    _emit_prefixed_clock_read(asm, "r25_wait")
    _emit_retire_expired(asm, "r25_wait")
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET), 0)
    asm.move_absw_to_dn(_r23._svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET), 1)
    asm.cmp_dn_w(2, 0)
    asm.branch_word(0x6500, "scheduler_wait")
    asm.branch_word(0x6200, "scheduler_due")
    asm.cmp_dn_w(3, 1)
    asm.branch_word(0x6500, "scheduler_wait")
    asm.label("scheduler_due")
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_RUNNING, _r23._svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))


def build_srk_saturn_midi_68k_r25_resident_audio_service_image(
    *, release_rate: int
) -> SaturnMidi68KR25ResidentAudioServiceImage:
    """Build one inert R25 image for an explicit candidate RR value."""

    plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=release_rate)
    validate_saturn_midi_68k_r25_resident_audio_layout()
    callbacks = (
        _r23._emit_audio_initialization,
        _r23._emit_audio_note_on,
        _r23._emit_audio_note_off,
        _r23._emit_audio_idle,
        _r23._emit_audio_wait_until_due,
        _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END,
    )
    try:
        _r23._emit_audio_initialization = lambda asm: _emit_r25_initialization(
            asm, eg1=plan.eg1_word, eg2=plan.eg2_word, rr=release_rate
        )
        _r23._emit_audio_note_on = _emit_r25_note_on
        _r23._emit_audio_note_off = _emit_r25_note_off
        _r23._emit_audio_idle = _emit_r25_idle
        _r23._emit_audio_wait_until_due = _emit_r25_wait_until_due
        _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END = SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END
        derived = _r23.build_srk_saturn_midi_68k_resident_audio_service_image()
    finally:
        (
            _r23._emit_audio_initialization,
            _r23._emit_audio_note_on,
            _r23._emit_audio_note_off,
            _r23._emit_audio_idle,
            _r23._emit_audio_wait_until_due,
            _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END,
        ) = callbacks
    image = SaturnMidi68KR25ResidentAudioServiceImage(
        release_rate=release_rate,
        eg1_word=plan.eg1_word,
        eg2_word=plan.eg2_word,
        words=derived.words,
    )
    if image.end_address > SATURN_MIDI_68K_R25_RESIDENT_AUDIO_MAX_END:
        raise SaturnMidi68KR25ResidentAudioServiceError(
            "R25 resident service exceeds reviewed 0x4000-0xA000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_r25_resident_audio_service_header(*, release_rate: int) -> str:
    image = build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=release_rate)
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R25_RESIDENT_AUDIO_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_R25_RESIDENT_AUDIO_SERVICE_H",
            "",
            f"#define SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R25_RESIDENT_AUDIO_STACK_ADDRESS 0x{SATURN_MIDI_68K_R25_RESIDENT_AUDIO_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_R25_RELEASE_RATE {release_rate}u",
            f"#define SRK_MIDI_68K_R25_EG1_WORD 0x{image.eg1_word:04X}u",
            f"#define SRK_MIDI_68K_R25_EG2_WORD 0x{image.eg2_word:04X}u",
            f"#define SRK_MIDI_68K_R25_TARGET_RELEASE_US {SATURN_MIDI_68K_R25_TARGET_RELEASE_US}UL",
            "",
            "extern const unsigned short srk_saturn_midi_68k_r25_resident_audio_service_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r25_voice_header() -> str:
    constants = {
        "VOICE_STATE_ADDRESS": SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS,
        "VOICE_STATE_BYTES": SATURN_MIDI_68K_R25_VOICE_STATE_BYTES,
        "MIXER_TABLE_ADDRESS": SATURN_MIDI_68K_R25_MIXER_TABLE_ADDRESS,
        "AUDIO_OWNERSHIP_END": SATURN_MIDI_68K_R25_AUDIO_OWNERSHIP_END,
    }
    lines = [
        "#ifndef SRK_SATURN_MIDI_68K_R25_VOICE_STATE_H",
        "#define SRK_SATURN_MIDI_68K_R25_VOICE_STATE_H",
        "",
    ]
    lines.extend(f"#define SRK_MIDI_68K_R25_{name} 0x{value:08X}UL" for name, value in constants.items())
    lines.extend(
        (
            f"#define SRK_MIDI_68K_R25_VOICE_MAGIC 0x{SATURN_MIDI_68K_R25_VOICE_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_R25_VOICE_VERSION {SATURN_MIDI_68K_R25_VOICE_VERSION}u",
            f"#define SRK_MIDI_68K_R25_OWNED_SLOTS {SATURN_MIDI_68K_R25_OWNED_SLOTS}u",
            f"#define SRK_MIDI_68K_R25_SLOT_BASE_WORD {SATURN_MIDI_68K_R25_SLOT_BASE_WORD}u",
            f"#define SRK_MIDI_68K_R25_SLOT_WORDS {SATURN_MIDI_68K_R25_SLOT_WORDS}u",
            f"#define SRK_MIDI_68K_R25_SLOT_PHASE_WORD {SATURN_MIDI_68K_R25_SLOT_PHASE_WORD}u",
            f"#define SRK_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD {SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD}u",
            f"#define SRK_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD {SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD}u",
            "",
            "#endif",
            "",
        )
    )
    return "\n".join(lines)


def render_srk_saturn_midi_68k_r25_resident_audio_service_source(*, release_rate: int) -> str:
    image = build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=release_rate)
    lines = [
        '#include "srk_saturn_midi_68k_r25_resident_audio_service.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_r25_resident_audio_service_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in image.words[index : index + 8]) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
