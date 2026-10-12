"""R23 resident MC68EC000 stream service with bounded SCSP slot-0 audio.

R22A is the immutable physical stream/scheduler baseline. R23 preserves that
mailbox, refill, timestamp and MIDI-state behavior while adding one deliberately
small audio surface: one non-stealing voice on SCSP slot 0, backed by the same
100-sample deterministic waveform used by SRK's physically exercised SH-2
Audio/SCSP diagnostic.

The first physical proof is intentionally monophonic. Polyphony, voice stealing,
sustain-held voices and full controller-to-mixer policy remain later work.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT,
    SATURN_MIDI_68K_CH_BANK_LSB,
    SATURN_MIDI_68K_CH_BANK_MSB,
    SATURN_MIDI_68K_CH_CHANNEL_PRESSURE,
    SATURN_MIDI_68K_CH_EVENT_COUNT,
    SATURN_MIDI_68K_CH_EXPRESSION,
    SATURN_MIDI_68K_CH_LAST_NOTE,
    SATURN_MIDI_68K_CH_LAST_OPCODE,
    SATURN_MIDI_68K_CH_LAST_POLY_NOTE,
    SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE,
    SATURN_MIDI_68K_CH_LAST_VELOCITY,
    SATURN_MIDI_68K_CH_PAN,
    SATURN_MIDI_68K_CH_PITCH_BEND,
    SATURN_MIDI_68K_CH_PROGRAM,
    SATURN_MIDI_68K_CH_SUSTAIN,
    SATURN_MIDI_68K_CH_VOLUME,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_STATE_ADDRESS,
)
from .midi_68k_resident_state_decoder import (
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION_OFFSET,
    _Assembler68K,
    _emit_active_count_decrement,
    _emit_active_count_increment,
    _emit_channel_dispatch,
    _emit_note_byte_address,
    _emit_record_byte_reads,
    _emit_record_validation,
    _emit_word_block,
    _state_displacement,
    build_srk_saturn_midi_68k_resident_state_initial_blocks,
)
from .midi_68k_resident_stream_service import (
    SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END,
    SATURN_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS,
    SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS,
    _MB_FLAGS,
    _MB_LAST_ERROR,
    _MB_MAGIC0,
    _MB_MAGIC1,
    _MB_QUEUE_CAPACITY,
    _MB_QUEUE_COUNT,
    _MB_READ_INDEX,
    _MB_READ_SEQUENCE,
    _MB_VERSION,
    _MB_WRITE_INDEX,
    _MB_WRITE_SEQUENCE,
    _emit_service_error,
    _emit_wait_until_due,
    _state_telemetry,
    _svc,
)
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_SEQUENCE_OFFSET,
    SATURN_MIDI_68K_STREAM_ERROR_CONTRACT,
    SATURN_MIDI_68K_STREAM_ERROR_COUNT,
    SATURN_MIDI_68K_STREAM_ERROR_EMPTY,
    SATURN_MIDI_68K_STREAM_ERROR_MAGIC,
    SATURN_MIDI_68K_STREAM_ERROR_RECORD,
    SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE,
    SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP,
    SATURN_MIDI_68K_STREAM_ERROR_VERSION,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
)
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END,
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_R23_OWNED_SLOTS,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_COMMON_ADDRESS,
    SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_SCSP_SLOT_BYTES,
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
    SATURN_MIDI_68K_VOICE_ACTIVE_WORD,
    SATURN_MIDI_68K_VOICE_CHANNEL_WORD,
    SATURN_MIDI_68K_VOICE_CONTROL_WORD,
    SATURN_MIDI_68K_VOICE_ERROR_BUSY,
    SATURN_MIDI_68K_VOICE_ERROR_NONE,
    SATURN_MIDI_68K_VOICE_GENERATION_WORD,
    SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD,
    SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD,
    SATURN_MIDI_68K_VOICE_MAGIC,
    SATURN_MIDI_68K_VOICE_MAGIC_WORD,
    SATURN_MIDI_68K_VOICE_MIXER_WORD,
    SATURN_MIDI_68K_VOICE_NOTE_WORD,
    SATURN_MIDI_68K_VOICE_OWNED_SLOTS_WORD,
    SATURN_MIDI_68K_VOICE_PITCH_WORD,
    SATURN_MIDI_68K_VOICE_SLOT_WORD,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
    SATURN_MIDI_68K_VOICE_VELOCITY_WORD,
    SATURN_MIDI_68K_VOICE_VERSION,
    SATURN_MIDI_68K_VOICE_VERSION_WORD,
    build_srk_saturn_midi_68k_pitch_table,
    build_srk_saturn_midi_68k_r23_waveform_words,
    midi_velocity_to_scsp_mixer,
    render_srk_saturn_midi_68k_voice_state_header,
)
from .midi_bridge import (
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_CAPACITY,
)
from .midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY
from .midi_program import SaturnMidiOpcode


SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS = SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS
SATURN_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS = SATURN_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS
SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END = SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END
SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS = SATURN_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS
SATURN_MIDI_68K_R23_PROOF_MIXER = midi_velocity_to_scsp_mixer(SATURN_MIDI_68K_R23_VELOCITY)


class SaturnMidi68KResidentAudioServiceError(RuntimeError):
    """Raised when the R23 resident audio image cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioServiceImage:
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return self.word_count * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


class _AudioAssembler68K(_Assembler68K):
    """Add the absolute-long LEA needed for the 68K SCSP register window."""

    def lea_absl_an(self, address: int, address_register: int) -> None:
        self._require_an(address_register)
        if address < 0 or address > 0xFFFFFFFF:
            raise SaturnMidi68KResidentAudioServiceError("absolute-long address out of range")
        self.word(0x41F9 + (address_register << 9))
        self.word((address >> 16) & 0xFFFF)
        self.word(address & 0xFFFF)


def _voice(word_index: int) -> int:
    return SATURN_MIDI_68K_VOICE_STATE_ADDRESS + word_index * 2


def _slot_byte_offset(word_index: int, slot: int = 0) -> int:
    return slot * SATURN_MIDI_68K_SCSP_SLOT_BYTES + word_index * 2


def _emit_audio_initialization(asm: _AudioAssembler68K) -> None:
    """Install deterministic PCM/pitch data and take bounded ownership of slot 0."""

    for index, word in enumerate(build_srk_saturn_midi_68k_r23_waveform_words()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS + index * 2)
    for index, word in enumerate(build_srk_saturn_midi_68k_pitch_table()):
        asm.move_imm_absw(word, SATURN_MIDI_68K_PITCH_TABLE_ADDRESS + index * 2)

    initial = (
        (SATURN_MIDI_68K_VOICE_MAGIC_WORD, SATURN_MIDI_68K_VOICE_MAGIC),
        (SATURN_MIDI_68K_VOICE_VERSION_WORD, SATURN_MIDI_68K_VOICE_VERSION),
        (SATURN_MIDI_68K_VOICE_OWNED_SLOTS_WORD, SATURN_MIDI_68K_R23_OWNED_SLOTS),
        (SATURN_MIDI_68K_VOICE_ACTIVE_WORD, 0),
        (SATURN_MIDI_68K_VOICE_SLOT_WORD, 0),
        (SATURN_MIDI_68K_VOICE_CHANNEL_WORD, 0xFFFF),
        (SATURN_MIDI_68K_VOICE_NOTE_WORD, 0xFFFF),
        (SATURN_MIDI_68K_VOICE_VELOCITY_WORD, 0),
        (SATURN_MIDI_68K_VOICE_GENERATION_WORD, 0),
        (SATURN_MIDI_68K_VOICE_PITCH_WORD, 0),
        (SATURN_MIDI_68K_VOICE_MIXER_WORD, 0),
        (SATURN_MIDI_68K_VOICE_CONTROL_WORD, SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP),
        (SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD, 0),
        (SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD, 0),
        (SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD, SATURN_MIDI_68K_VOICE_ERROR_NONE),
    )
    for word_index, value in initial:
        asm.move_imm_absw(value, _voice(word_index))

    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_REGISTER_BASE, 4)
    asm.lea_absl_an(SATURN_MIDI_68K_SCSP_COMMON_ADDRESS, 5)
    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_COMMON_RESET_VALUE, 0)
    asm.move_dn_d16_an(0, 0, 5)

    # Match the known-good SH-2 diagnostic's conservative global key-off pass.
    for slot in range(SATURN_MIDI_68K_SCSP_SLOT_COUNT):
        offset = _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL, slot)
        asm.move_d16_an_to_dn(4, offset, 0)
        asm.andi_w(0xFFFF ^ SATURN_MIDI_68K_SCSP_CONTROL_KYONB, 0)
        asm.move_dn_d16_an(0, offset, 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL), 4)

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
    for word_index, value in slot_values:
        asm.move_imm_to_dn(value, 0)
        asm.move_dn_d16_an(0, _slot_byte_offset(word_index), 4)


def _emit_audio_note_on(asm: _AudioAssembler68K) -> None:
    """Allocate/retrigger slot 0 from D1=channel, D5=note, D7=velocity."""

    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_ACTIVE_WORD), 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, "audio_note_on_free")
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_CHANNEL_WORD), 0)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6600, "audio_note_on_busy")
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_NOTE_WORD), 0)
    asm.cmp_dn_w(5, 0)
    asm.branch_word(0x6600, "audio_note_on_busy")
    asm.branch_word(0x6000, "audio_note_on_free")

    asm.label("audio_note_on_busy")
    asm.move_imm_absw(SATURN_MIDI_68K_VOICE_ERROR_BUSY, _voice(SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD))
    asm.branch_word(0x6000, "audio_note_on_done")

    asm.label("audio_note_on_free")
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_GENERATION_WORD), 0)
    asm.addq_w(1, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, "audio_generation_ready")
    asm.move_imm_to_dn(1, 0)
    asm.label("audio_generation_ready")
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_GENERATION_WORD))

    asm.move_imm_absw(1, _voice(SATURN_MIDI_68K_VOICE_ACTIVE_WORD))
    asm.move_dn_absw(1, _voice(SATURN_MIDI_68K_VOICE_CHANNEL_WORD))
    asm.move_dn_absw(5, _voice(SATURN_MIDI_68K_VOICE_NOTE_WORD))
    asm.move_dn_absw(7, _voice(SATURN_MIDI_68K_VOICE_VELOCITY_WORD))
    asm.move_imm_absw(SATURN_MIDI_68K_VOICE_ERROR_NONE, _voice(SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD))

    asm.lea_absw_an(SATURN_MIDI_68K_PITCH_TABLE_ADDRESS, 5)
    asm.move_dn_to_dn(5, 0)
    asm.add_w_dn_to_dn(0, 0)
    asm.adda_w_dn_an(0, 5)
    asm.move_d16_an_to_dn(5, 0, 0)
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_PITCH_WORD))
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_PITCH), 4)

    # R23 proves note allocation/keying first. Velocity/expression scaling is
    # deliberately deferred; the proof velocity maps to this reviewed level.
    asm.move_imm_to_dn(SATURN_MIDI_68K_R23_PROOF_MIXER, 0)
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_MIXER_WORD))
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER), 4)

    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
        0,
    )
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_CONTROL_WORD))
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL), 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONB
        | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL), 4)

    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD))
    asm.label("audio_note_on_done")


def _emit_audio_note_off(asm: _AudioAssembler68K, prefix: str) -> None:
    """Release slot 0 only when D1/D5 match its owner."""

    done = f"{prefix}_done"
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_ACTIVE_WORD), 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, done)
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_CHANNEL_WORD), 0)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6600, done)
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_NOTE_WORD), 0)
    asm.cmp_dn_w(5, 0)
    asm.branch_word(0x6600, done)

    asm.move_imm_to_dn(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, 0)
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL), 4)
    asm.move_imm_to_dn(
        SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONEX,
        0,
    )
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_CONTROL), 4)
    asm.move_imm_to_dn(0, 0)
    asm.move_dn_d16_an(0, _slot_byte_offset(SATURN_MIDI_68K_SCSP_SLOT_MIXER), 4)

    asm.move_imm_absw(0, _voice(SATURN_MIDI_68K_VOICE_ACTIVE_WORD))
    asm.move_imm_absw(0, _voice(SATURN_MIDI_68K_VOICE_VELOCITY_WORD))
    asm.move_imm_absw(0, _voice(SATURN_MIDI_68K_VOICE_MIXER_WORD))
    asm.move_imm_absw(SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP, _voice(SATURN_MIDI_68K_VOICE_CONTROL_WORD))
    asm.move_absw_to_dn(_voice(SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _voice(SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD))
    asm.label(done)


def _emit_audio_idle(asm: _AudioAssembler68K) -> None:
    """Optional derived-service work while the mailbox has no fresh batch.

    The accepted R23 implementation intentionally emits nothing.  Later audio
    revisions can temporarily replace this callback while deriving a fresh
    image without changing the physically accepted R23 binary.
    """


def _emit_audio_wait_until_due(asm: _AudioAssembler68K) -> None:
    """Optional derived-service scheduler hook; R23 remains byte-identical."""

    _emit_wait_until_due(asm)


def _emit_audio_state_mutation_dispatch(asm: _AudioAssembler68K) -> None:
    """Apply R22A MIDI state semantics plus R23 slot-0 audio actions."""

    _emit_channel_dispatch(asm)
    # R22A reuses D4 for event-count bookkeeping after dispatch. Preserve the
    # original MIDI channel in D1 for the R23 voice owner checks.
    asm.move_dn_to_dn(4, 1)

    asm.move_d16_an_to_dn(1, _state_displacement(SATURN_MIDI_68K_CH_EVENT_COUNT), 4)
    asm.addq_w(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_EVENT_COUNT), 1)
    asm.move_dn_d16_an(6, _state_displacement(SATURN_MIDI_68K_CH_LAST_OPCODE), 1)

    for opcode, label in (
        (SaturnMidiOpcode.NOTE_OFF, "stream_op_note_off"),
        (SaturnMidiOpcode.NOTE_ON, "stream_op_note_on"),
        (SaturnMidiOpcode.POLY_AFTERTOUCH, "stream_op_poly_aftertouch"),
        (SaturnMidiOpcode.CONTROL_CHANGE, "stream_op_control_change"),
        (SaturnMidiOpcode.PROGRAM_CHANGE, "stream_op_program_change"),
        (SaturnMidiOpcode.CHANNEL_PRESSURE, "stream_op_channel_pressure"),
        (SaturnMidiOpcode.PITCH_BEND, "stream_op_pitch_bend"),
    ):
        asm.cmpi_w(int(opcode), 6)
        asm.branch_word(0x6700, label)
    asm.branch_word(0x6000, "error_record")

    asm.label("stream_op_note_off")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_VELOCITY), 1)
    _emit_audio_note_off(asm, "audio_note_off")
    _emit_note_byte_address(asm, "stream_note_off")
    asm.bclr_dn_an_indirect(5, 3)
    _emit_active_count_decrement(asm, "stream_note_off_count_done")
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_note_on")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_VELOCITY), 1)
    asm.cmpi_w(0, 7)
    asm.branch_word(0x6700, "stream_note_on_zero_velocity")
    _emit_audio_note_on(asm)
    _emit_note_byte_address(asm, "stream_note_on")
    asm.bset_dn_an_indirect(5, 3)
    _emit_active_count_increment(asm, "stream_note_on_count_done")
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_note_on_zero_velocity")
    _emit_audio_note_off(asm, "audio_note_on_zero_off")
    _emit_note_byte_address(asm, "stream_note_on_zero")
    asm.bclr_dn_an_indirect(5, 3)
    _emit_active_count_decrement(asm, "stream_note_on_zero_count_done")
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_poly_aftertouch")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_POLY_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE), 1)
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_control_change")
    asm.adda_w_dn_an(5, 2)
    asm.move_b_dn_an_indirect(7, 2)
    for controller, label in (
        (0, "stream_cc_bank_msb"),
        (32, "stream_cc_bank_lsb"),
        (7, "stream_cc_volume"),
        (10, "stream_cc_pan"),
        (11, "stream_cc_expression"),
        (64, "stream_cc_sustain"),
    ):
        asm.cmpi_w(controller, 5)
        asm.branch_word(0x6700, label)
    asm.branch_word(0x6000, "stream_record_done")

    for label, field in (
        ("stream_cc_bank_msb", SATURN_MIDI_68K_CH_BANK_MSB),
        ("stream_cc_bank_lsb", SATURN_MIDI_68K_CH_BANK_LSB),
        ("stream_cc_volume", SATURN_MIDI_68K_CH_VOLUME),
        ("stream_cc_pan", SATURN_MIDI_68K_CH_PAN),
        ("stream_cc_expression", SATURN_MIDI_68K_CH_EXPRESSION),
    ):
        asm.label(label)
        asm.move_dn_d16_an(7, _state_displacement(field), 1)
        asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_cc_sustain")
    asm.cmpi_w(64, 7)
    asm.branch_word(0x6500, "stream_cc_sustain_off")
    asm.move_imm_to_dn(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_SUSTAIN), 1)
    asm.branch_word(0x6000, "stream_record_done")
    asm.label("stream_cc_sustain_off")
    asm.move_imm_to_dn(0, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_SUSTAIN), 1)
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_program_change")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_PROGRAM), 1)
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_channel_pressure")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_CHANNEL_PRESSURE), 1)
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_pitch_bend")
    for _ in range(7):
        asm.add_w_dn_to_dn(7, 7)
    asm.add_w_dn_to_dn(5, 7)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_PITCH_BEND), 1)
    asm.branch_word(0x6000, "stream_record_done")


def build_srk_saturn_midi_68k_resident_audio_service_image() -> SaturnMidi68KResidentAudioServiceImage:
    """Build R22A-compatible streaming plus monophonic SCSP slot-0 audio."""

    if SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS != 32:
        raise SaturnMidi68KResidentAudioServiceError("reviewed queue capacity changed")

    summary_words, controller_words, active_note_words = (
        build_srk_saturn_midi_68k_resident_state_initial_blocks()
    )
    asm = _AudioAssembler68K()

    _emit_word_block(asm, SATURN_MIDI_68K_STATE_ADDRESS, summary_words)
    _emit_word_block(asm, SATURN_MIDI_68K_CONTROLLER_ADDRESS, controller_words)
    _emit_word_block(asm, SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, active_note_words)
    _emit_audio_initialization(asm)

    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_SERVICE_MAGIC, _svc(SATURN_MIDI_68K_STREAM_MAGIC_OFFSET))
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_SERVICE_VERSION, _svc(SATURN_MIDI_68K_STREAM_VERSION_OFFSET))
    for offset in (
        SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
        SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
        SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
        SATURN_MIDI_68K_STREAM_CURRENT_SEQUENCE_OFFSET,
        SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
        SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET,
        SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET,
        SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET,
        SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET,
        SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
        SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET,
        SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET,
        SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET,
    ):
        asm.move_imm_absw(0, _svc(offset))
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))

    asm.move_imm_absw(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC_OFFSET))
    asm.move_imm_absw(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION_OFFSET))
    for offset in (
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET,
    ):
        asm.move_imm_absw(0, _state_telemetry(offset))
    asm.move_imm_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _MB_LAST_ERROR)

    asm.label("poll_batch")
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
    _emit_audio_idle(asm)
    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_word(0x6700, "poll_batch")

    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_absw_to_dn(_MB_READ_SEQUENCE, 1)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6700, "poll_batch")

    asm.cmpi_w(0, 1)
    asm.branch_word(0x6700, "expect_first_sequence")
    asm.addq_w(1, 1)
    asm.cmpi_w(0, 1)
    asm.branch_word(0x6600, "compare_expected_sequence")
    asm.move_imm_to_dn(1, 1)
    asm.branch_word(0x6000, "compare_expected_sequence")
    asm.label("expect_first_sequence")
    asm.move_imm_to_dn(1, 1)
    asm.label("compare_expected_sequence")
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6600, "error_sequence")

    asm.move_absw_to_dn(_MB_MAGIC0, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_MAGIC0, 0)
    asm.branch_word(0x6600, "error_magic")
    asm.move_absw_to_dn(_MB_MAGIC1, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_MAGIC1, 0)
    asm.branch_word(0x6600, "error_magic")
    asm.move_absw_to_dn(_MB_VERSION, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_VERSION, 0)
    asm.branch_word(0x6600, "error_version")
    asm.move_absw_to_dn(_MB_QUEUE_CAPACITY, 0)
    asm.cmpi_w(SATURN_MIDI_QUEUE_CAPACITY, 0)
    asm.branch_word(0x6600, "error_contract")
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, "error_empty")
    asm.cmpi_w(SATURN_MIDI_QUEUE_CAPACITY, 0)
    asm.branch_word(0x6200, "error_count")
    asm.move_absw_to_dn(_MB_WRITE_INDEX, 1)
    asm.cmp_dn_w(0, 1)
    asm.branch_word(0x6600, "error_count")

    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET), 0)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET), 1)
    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)
    asm.label("validation_loop")
    _emit_record_byte_reads(asm)
    _emit_record_validation(asm)
    asm.cmp_dn_w(0, 2)
    asm.branch_word(0x6500, "error_timestamp")
    asm.branch_word(0x6200, "validation_time_ok")
    asm.cmp_dn_w(1, 3)
    asm.branch_word(0x6500, "error_timestamp")
    asm.label("validation_time_ok")
    asm.move_dn_to_dn(2, 0)
    asm.move_dn_to_dn(3, 1)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET), 4)
    asm.addq_w(1, 4)
    asm.move_dn_absw(4, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 5)
    asm.cmp_dn_w(5, 4)
    asm.branch_word(0x6600, "validation_loop")

    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)

    asm.label("schedule_record")
    _emit_record_byte_reads(asm)
    _emit_audio_wait_until_due(asm)
    _emit_audio_state_mutation_dispatch(asm)

    asm.label("stream_record_done")
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET), 4)
    asm.addq_w(1, 4)
    asm.move_dn_absw(4, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.move_dn_absw(4, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET))
    asm.move_dn_absw(4, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET))
    asm.move_dn_absw(2, _svc(SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET))
    asm.move_dn_absw(3, _svc(SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET))
    asm.move_dn_absw(2, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET))
    asm.move_dn_absw(3, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET))

    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET))
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6600, "total_increment_done")
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET))
    asm.label("total_increment_done")

    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 5)
    asm.cmp_dn_w(5, 4)
    asm.branch_word(0x6600, "schedule_record")

    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_SEQUENCE_OFFSET))
    asm.move_dn_absw(4, _MB_READ_INDEX)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET))
    asm.move_imm_absw(0, _MB_LAST_ERROR)
    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET))
    asm.move_imm_absw(1, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.branch_word(0x6000, "poll_batch")

    _emit_service_error(asm, "error_magic", SATURN_MIDI_68K_STREAM_ERROR_MAGIC)
    _emit_service_error(asm, "error_version", SATURN_MIDI_68K_STREAM_ERROR_VERSION)
    _emit_service_error(asm, "error_contract", SATURN_MIDI_68K_STREAM_ERROR_CONTRACT)
    _emit_service_error(asm, "error_empty", SATURN_MIDI_68K_STREAM_ERROR_EMPTY)
    _emit_service_error(asm, "error_count", SATURN_MIDI_68K_STREAM_ERROR_COUNT)
    _emit_service_error(asm, "error_record", SATURN_MIDI_68K_STREAM_ERROR_RECORD)
    _emit_service_error(asm, "error_sequence", SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE)
    _emit_service_error(asm, "error_timestamp", SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP)

    image = SaturnMidi68KResidentAudioServiceImage(words=asm.finish())
    if image.end_address > SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_END:
        raise SaturnMidi68KResidentAudioServiceError(
            "R23 resident audio service exceeds reviewed 0x4000-0x8000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_resident_audio_service_header() -> str:
    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_AUDIO_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_AUDIO_SERVICE_H",
            "",
            f"#define SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS {SATURN_MIDI_68K_RESIDENT_AUDIO_MAX_RECORDS}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_resident_audio_service_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_audio_service_source() -> str:
    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    lines = [
        '#include "srk_saturn_midi_68k_resident_audio_service.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_resident_audio_service_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        row = image.words[index : index + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in row) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)


def render_srk_saturn_midi_68k_resident_audio_voice_header() -> str:
    return render_srk_saturn_midi_68k_voice_state_header()
