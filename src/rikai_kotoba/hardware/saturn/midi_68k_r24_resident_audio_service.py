"""R24 two-slot resident MC68EC000 MIDI -> SCSP service.

R23 is an immutable physical one-voice audio baseline.  R24 derives a new
resident image without modifying that accepted source: it preserves the R22A/R23
mailbox, refill, timestamp and MIDI-state engine, replaces only the audio
initialisation/keying callbacks during image construction, and restores the R23
module immediately afterwards.

The new hardware contract owns SCSP slots 0 and 1, uses the physically proven
100-sample PCM loop, installs the calibrated R24 MIDI-note pitch table, and adds
a 128-entry velocity/mixer table.  There is no voice stealing.  The selected
CC0 reference song peaks at exactly two simultaneous notes, so any third voice
is a deterministic BUSY error rather than an implicit policy change.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from . import midi_68k_resident_audio_service as _r23
from .midi_68k_r24_pitch import build_saturn_midi_68k_r24_pitch_table
from .midi_68k_r24_voice_allocator import (
    SATURN_MIDI_68K_R24_OWNED_SLOTS,
    SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY,
    SATURN_MIDI_68K_R24_VOICE_ERROR_NONE,
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
    build_srk_saturn_midi_68k_r23_waveform_words,
    midi_velocity_to_scsp_mixer,
)


SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS = (
    _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS
)
SATURN_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS = (
    _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS
)
SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_END = _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END
SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_RECORDS = (
    _r23.SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS
)

SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS = 0x00002300
SATURN_MIDI_68K_R24_VOICE_STATE_BYTES = 0x00000100
SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS = 0x00002400
SATURN_MIDI_68K_R24_MIXER_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END = 0x00002500

SATURN_MIDI_68K_R24_VOICE_MAGIC = 0x5632  # "V2"
SATURN_MIDI_68K_R24_VOICE_VERSION = 1

# Global words in the R24 0x2300 voice ledger.
SATURN_MIDI_68K_R24_VOICE_MAGIC_WORD = 0
SATURN_MIDI_68K_R24_VOICE_VERSION_WORD = 1
SATURN_MIDI_68K_R24_VOICE_OWNED_SLOTS_WORD = 2
SATURN_MIDI_68K_R24_VOICE_GENERATION_WORD = 3
SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD = 4
SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD = 5
SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD = 6
SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD = 7
SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD = 8
SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD = 9

# Eight words per owned slot, starting at word 16.
SATURN_MIDI_68K_R24_SLOT_BASE_WORD = 16
SATURN_MIDI_68K_R24_SLOT_WORDS = 8
SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD = 0
SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD = 1
SATURN_MIDI_68K_R24_SLOT_NOTE_WORD = 2
SATURN_MIDI_68K_R24_SLOT_VELOCITY_WORD = 3
SATURN_MIDI_68K_R24_SLOT_GENERATION_WORD = 4
SATURN_MIDI_68K_R24_SLOT_PITCH_WORD = 5
SATURN_MIDI_68K_R24_SLOT_MIXER_WORD = 6
SATURN_MIDI_68K_R24_SLOT_CONTROL_WORD = 7


class SaturnMidi68KR24ResidentAudioServiceError(RuntimeError):
    """Raised when the R24 resident audio image cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KR24ResidentAudioServiceImage:
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return self.word_count * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


def _global(word_index: int) -> int:
    return SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS + word_index * 2


def _slot_word(slot: int, field: int) -> int:
    if slot < 0 or slot >= SATURN_MIDI_68K_R24_OWNED_SLOTS:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 slot escapes owned range")
    if field < 0 or field >= SATURN_MIDI_68K_R24_SLOT_WORDS:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 slot field escapes ledger")
    index = SATURN_MIDI_68K_R24_SLOT_BASE_WORD + slot * SATURN_MIDI_68K_R24_SLOT_WORDS + field
    return SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS + index * 2


def build_saturn_midi_68k_r24_mixer_table() -> tuple[int, ...]:
    table = tuple(midi_velocity_to_scsp_mixer(value) for value in range(128))
    if len(table) != 128:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 mixer table changed size")
    if table[0] != 0:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 velocity zero must remain silent")
    return table


def validate_saturn_midi_68k_r24_resident_audio_layout() -> None:
    if SATURN_MIDI_68K_R24_OWNED_SLOTS != 2:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 must own exactly two SCSP slots")
    pitch_end = SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + 128 * 2
    if pitch_end != SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 pitch table/voice ledger boundary changed")
    if (
        SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS + SATURN_MIDI_68K_R24_VOICE_STATE_BYTES
        != SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS
    ):
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 voice ledger/mixer boundary changed")
    if (
        SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS + SATURN_MIDI_68K_R24_MIXER_TABLE_BYTES
        != SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END
    ):
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 mixer ownership boundary changed")
    if SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END > SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS:
        raise SaturnMidi68KR24ResidentAudioServiceError("R24 audio data overlaps resident program")


def _emit_r24_audio_initialization(asm: _r23._AudioAssembler68K) -> None:
    """Install the shared waveform, calibrated tables and two bounded SCSP slots."""

    validate_saturn_midi_68k_r24_resident_audio_layout()
    for index, word in enumerate(build_srk_saturn_midi_68k_r23_waveform_words()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS + index * 2)
    for index, word in enumerate(build_saturn_midi_68k_r24_pitch_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + index * 2)
    for index, word in enumerate(build_saturn_midi_68k_r24_mixer_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS + index * 2)

    globals_initial = (
        (SATURN_MIDI_68K_R24_VOICE_MAGIC_WORD, SATURN_MIDI_68K_R24_VOICE_MAGIC),
        (SATURN_MIDI_68K_R24_VOICE_VERSION_WORD, SATURN_MIDI_68K_R24_VOICE_VERSION),
        (SATURN_MIDI_68K_R24_VOICE_OWNED_SLOTS_WORD, SATURN_MIDI_68K_R24_OWNED_SLOTS),
        (SATURN_MIDI_68K_R24_VOICE_GENERATION_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD, 0),
        (SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD, SATURN_MIDI_68K_R24_VOICE_ERROR_NONE),
    )
    for word_index, value in globals_initial:
        asm.move_imm_absw(value, _global(word_index))

    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        initial = (
            (SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD, 0),
            (SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD, 0xFFFF),
            (SATURN_MIDI_68K_R24_SLOT_NOTE_WORD, 0xFFFF),
            (SATURN_MIDI_68K_R24_SLOT_VELOCITY_WORD, 0),
            (SATURN_MIDI_68K_R24_SLOT_GENERATION_WORD, 0),
            (SATURN_MIDI_68K_R24_SLOT_PITCH_WORD, 0),
            (SATURN_MIDI_68K_R24_SLOT_MIXER_WORD, 0),
            (SATURN_MIDI_68K_R24_SLOT_CONTROL_WORD, SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP),
        )
        for field, value in initial:
            asm.move_imm_absw(value, _slot_word(slot, field))

    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_REGISTER_BASE, 4)
    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_COMMON_ADDRESS, 5)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE, 0)
    asm.move_dn_d16_an(0, 0, 5)

    # Preserve the physically accepted R23 conservative global key-off pass.
    for slot in range(SATURN_MIDI_68K_SCSP_SLOT_COUNT):
        offset = _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot)
        asm.move_d16_an_to_dn(4, offset, 0)
        asm.andi_w(0xFFFF ^ SATURN_MIDI_68K_SCSP_CONTROL_KYONB, 0)
        asm.move_dn_d16_an(0, offset, 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, 0), 4)

    slot_values = (
        (SATURN_MIDI_68K_SCSP_SLOT_CONTROL, SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP),
        (SATURN_MIDI_68K_SCSP_SLOT_SA_LOW, SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS),
        (SATURN_MIDI_68K_SCSP_SLOT_LSA, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_LEA, SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END),
        (SATURN_MIDI_68K_SCSP_SLOT_EG1, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_EG2, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_TL, SATURN_MIDI_68K_SCSP_SOUND_DIRECT),
        (SATURN_MIDI_68K_SCSP_SLOT_FM, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_PITCH, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_LFO, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_DSP, 0),
        (SATURN_MIDI_68K_SCSP_SLOT_MIXER, 0),
    )
    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        for word_index, value in slot_values:
            asm.move_imm_to_dn(value, 0)
            asm.move_dn_d16_an(0, _r23._slot_byte_offset(word_index, slot), 4)


def _emit_r24_active_increment(
    asm: _r23._AudioAssembler68K,
    *,
    prefix: str,
) -> None:
    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD))
    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD), 2)
    asm.cmp_dn_w(2, 0)
    asm.branch_word(0x6300, f"{prefix}_peak_done")  # BLS: active <= peak
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD))
    asm.label(f"{prefix}_peak_done")


def _emit_r24_key_on_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    new_allocation: bool,
) -> None:
    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_GENERATION_WORD), 0)
    asm.addq_w(1, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, f"{prefix}_generation_ready")
    asm.move_imm_to_dn(1, 0)
    asm.label(f"{prefix}_generation_ready")
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_GENERATION_WORD))
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_GENERATION_WORD))

    asm.move_imm_absw(1, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD))
    asm.move_dn_absw(1, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD))
    asm.move_dn_absw(5, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_NOTE_WORD))
    asm.move_dn_absw(7, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_VELOCITY_WORD))

    asm.lea_absw_an(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_PITCH_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_PITCH, slot), 4)

    asm.lea_absw_an(SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(7, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_MIXER_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER, slot), 4)

    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
        0,
    )
    asm.move_dn_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_CONTROL_WORD))
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONB
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)

    if new_allocation:
        _emit_r24_active_increment(asm, prefix=prefix)

    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD))
    asm.move_imm_absw(
        SATURN_MIDI_68K_R24_VOICE_ERROR_NONE,
        _global(SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD),
    )
    asm.branch_word(0x6000, "r24_audio_note_on_done")


def _emit_r24_audio_note_on(asm: _r23._AudioAssembler68K) -> None:
    """Retrigger matching key or allocate the lowest free of SCSP slots 0/1."""

    # Matching active key wins before free-slot allocation.
    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD), 0)
        asm.cmpi_w(0, 0)
        asm.branch_word(0x6700, f"r24_note_on_match_next_{slot}")
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD), 0)
        asm.cmp_dn_w(1, 0)
        asm.branch_word(0x6600, f"r24_note_on_match_next_{slot}")
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_NOTE_WORD), 0)
        asm.cmp_dn_w(5, 0)
        asm.branch_word(0x6700, f"r24_note_on_slot_{slot}_retrigger")
        asm.label(f"r24_note_on_match_next_{slot}")

    # Lowest free slot wins.
    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD), 0)
        asm.cmpi_w(0, 0)
        asm.branch_word(0x6700, f"r24_note_on_slot_{slot}_free")

    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD))
    asm.move_imm_absw(
        SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY,
        _global(SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD),
    )
    asm.branch_word(0x6000, "r24_audio_note_on_done")

    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        asm.label(f"r24_note_on_slot_{slot}_retrigger")
        _emit_r24_key_on_slot(
            asm,
            slot,
            prefix=f"r24_note_on_slot_{slot}_retrigger",
            new_allocation=False,
        )
        asm.label(f"r24_note_on_slot_{slot}_free")
        _emit_r24_key_on_slot(
            asm,
            slot,
            prefix=f"r24_note_on_slot_{slot}_free",
            new_allocation=True,
        )

    asm.label("r24_audio_note_on_done")


def _emit_r24_release_slot(
    asm: _r23._AudioAssembler68K,
    slot: int,
    *,
    prefix: str,
    done: str,
) -> None:
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, 0)
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot), 4)
    asm.move_imm_to_dn(0, 0)
    asm.move_dn_d16_an(0, _r23._slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER, slot), 4)

    asm.move_imm_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD))
    asm.move_imm_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_VELOCITY_WORD))
    asm.move_imm_absw(0, _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_MIXER_WORD))
    asm.move_imm_absw(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
        _slot_word(slot, SATURN_MIDI_68K_R24_SLOT_CONTROL_WORD),
    )

    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD))
    asm.move_absw_to_dn(_global(SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD), 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, f"{prefix}_active_done")
    asm.subq_w(1, 0)
    asm.move_dn_absw(0, _global(SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD))
    asm.label(f"{prefix}_active_done")
    asm.move_imm_absw(
        SATURN_MIDI_68K_R24_VOICE_ERROR_NONE,
        _global(SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD),
    )
    asm.branch_word(0x6000, done)


def _emit_r24_audio_note_off(asm: _r23._AudioAssembler68K, prefix: str) -> None:
    """Release whichever owned slot currently owns D1=channel/D5=note."""

    done = f"{prefix}_r24_done"
    for slot in range(SATURN_MIDI_68K_R24_OWNED_SLOTS):
        next_label = f"{prefix}_r24_next_{slot}"
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD), 0)
        asm.cmpi_w(0, 0)
        asm.branch_word(0x6700, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD), 0)
        asm.cmp_dn_w(1, 0)
        asm.branch_word(0x6600, next_label)
        asm.move_absw_to_dn(_slot_word(slot, SATURN_MIDI_68K_R24_SLOT_NOTE_WORD), 0)
        asm.cmp_dn_w(5, 0)
        asm.branch_word(0x6600, next_label)
        _emit_r24_release_slot(
            asm,
            slot,
            prefix=f"{prefix}_r24_release_{slot}",
            done=done,
        )
        asm.label(next_label)
    asm.label(done)


def build_srk_saturn_midi_68k_r24_resident_audio_service_image() -> SaturnMidi68KR24ResidentAudioServiceImage:
    """Derive the R24 two-slot image while restoring the immutable R23 generator."""

    validate_saturn_midi_68k_r24_resident_audio_layout()
    original_initialization = _r23._emit_audio_initialization
    original_note_on = _r23._emit_audio_note_on
    original_note_off = _r23._emit_audio_note_off
    try:
        _r23._emit_audio_initialization = _emit_r24_audio_initialization
        _r23._emit_audio_note_on = _emit_r24_audio_note_on
        _r23._emit_audio_note_off = _emit_r24_audio_note_off
        derived = _r23.build_srk_saturn_midi_68k_resident_audio_service_image()
    finally:
        _r23._emit_audio_initialization = original_initialization
        _r23._emit_audio_note_on = original_note_on
        _r23._emit_audio_note_off = original_note_off

    image = SaturnMidi68KR24ResidentAudioServiceImage(words=derived.words)
    if image.end_address > SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_END:
        raise SaturnMidi68KR24ResidentAudioServiceError(
            "R24 resident audio service exceeds reviewed 0x4000-0x8000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_r24_resident_audio_service_header() -> str:
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R24_RESIDENT_AUDIO_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_R24_RESIDENT_AUDIO_SERVICE_H",
            "",
            f"#define SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS 0x{SATURN_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_R24_RESIDENT_AUDIO_MAX_RECORDS {SATURN_MIDI_68K_R24_RESIDENT_AUDIO_MAX_RECORDS}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_r24_resident_audio_service_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r24_voice_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R24_VOICE_STATE_H",
            "#define SRK_SATURN_MIDI_68K_R24_VOICE_STATE_H",
            "",
            f"#define SRK_MIDI_68K_R24_VOICE_STATE_ADDRESS 0x{SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R24_VOICE_STATE_BYTES 0x{SATURN_MIDI_68K_R24_VOICE_STATE_BYTES:08X}UL",
            f"#define SRK_MIDI_68K_R24_MIXER_TABLE_ADDRESS 0x{SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_R24_AUDIO_OWNERSHIP_END 0x{SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END:08X}UL",
            f"#define SRK_MIDI_68K_R24_VOICE_MAGIC 0x{SATURN_MIDI_68K_R24_VOICE_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_R24_VOICE_VERSION {SATURN_MIDI_68K_R24_VOICE_VERSION}u",
            f"#define SRK_MIDI_68K_R24_OWNED_SLOTS {SATURN_MIDI_68K_R24_OWNED_SLOTS}u",
            f"#define SRK_MIDI_68K_R24_VOICE_GENERATION_WORD {SATURN_MIDI_68K_R24_VOICE_GENERATION_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD {SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD {SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD {SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD {SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD {SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD}u",
            f"#define SRK_MIDI_68K_R24_VOICE_LAST_ERROR_WORD {SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_BASE_WORD {SATURN_MIDI_68K_R24_SLOT_BASE_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_WORDS {SATURN_MIDI_68K_R24_SLOT_WORDS}u",
            f"#define SRK_MIDI_68K_R24_SLOT_ACTIVE_WORD {SATURN_MIDI_68K_R24_SLOT_ACTIVE_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_CHANNEL_WORD {SATURN_MIDI_68K_R24_SLOT_CHANNEL_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_NOTE_WORD {SATURN_MIDI_68K_R24_SLOT_NOTE_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_VELOCITY_WORD {SATURN_MIDI_68K_R24_SLOT_VELOCITY_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_GENERATION_WORD {SATURN_MIDI_68K_R24_SLOT_GENERATION_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_PITCH_WORD {SATURN_MIDI_68K_R24_SLOT_PITCH_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_MIXER_WORD {SATURN_MIDI_68K_R24_SLOT_MIXER_WORD}u",
            f"#define SRK_MIDI_68K_R24_SLOT_CONTROL_WORD {SATURN_MIDI_68K_R24_SLOT_CONTROL_WORD}u",
            f"#define SRK_MIDI_68K_SCSP_REGISTER_BASE 0x{SATURN_MIDI_68K_SCSP_REGISTER_BASE:08X}UL",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r24_resident_audio_service_source() -> str:
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    lines = [
        '#include "srk_saturn_midi_68k_r24_resident_audio_service.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_r24_resident_audio_service_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        row = image.words[index : index + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in row) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
