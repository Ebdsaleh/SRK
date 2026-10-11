"""Resident MC68EC000 multi-batch/refill service with timestamp gating.

R21 physically accepted the Phase-B state-mutating decoder.  This new image
preserves R21 unchanged and turns those semantics into a continuous resident
service: state is initialized once, successive 1..32-record batches are
accepted through strict non-zero mailbox sequences, timestamps remain
chronological across refill boundaries, and each record is applied only after
a stable producer-published microsecond clock reaches its due time.

The image remains silent.  It never touches SCSP playback registers.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL,
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
    SATURN_MIDI_68K_CHANNEL_COUNT,
    SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_COUNT,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
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
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET,
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
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAG_RUNNING,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
)
from .midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_CAPACITY,
)
from .midi_mailbox import SATURN_MIDI_MAILBOX_FLAG_READY
from .midi_program import SaturnMidiOpcode


SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS = 0x00004000
SATURN_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END = 0x00008000
SATURN_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS = SATURN_MIDI_QUEUE_CAPACITY

_MB_MAGIC0 = SATURN_MIDI_MAILBOX_ADDRESS + 0
_MB_MAGIC1 = SATURN_MIDI_MAILBOX_ADDRESS + 2
_MB_VERSION = SATURN_MIDI_MAILBOX_ADDRESS + 4
_MB_FLAGS = SATURN_MIDI_MAILBOX_ADDRESS + 6
_MB_WRITE_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 8
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_WRITE_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 12
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_QUEUE_CAPACITY = SATURN_MIDI_MAILBOX_ADDRESS + 16
_MB_QUEUE_COUNT = SATURN_MIDI_MAILBOX_ADDRESS + 18
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20


class SaturnMidi68KResidentStreamServiceError(RuntimeError):
    """Raised when the continuous resident service cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamServiceImage:
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return self.word_count * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


def _svc(offset: int) -> int:
    return SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS + offset


def _state_telemetry(offset: int) -> int:
    return SATURN_MIDI_68K_TELEMETRY_ADDRESS + offset


def _emit_service_error(asm: _Assembler68K, label: str, error_code: int) -> None:
    asm.label(label)
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_ERROR, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
    asm.move_imm_absw(error_code, _svc(SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET))
    asm.move_imm_absw(error_code, _MB_LAST_ERROR)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.branch_short_self()


def _emit_stable_clock_read(asm: _Assembler68K) -> None:
    """Leave one stable producer clock sample in D0:D1 (high:low)."""

    asm.label("clock_read_retry")
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET), 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET))
    asm.andi_w(1, 0)
    asm.branch_word(0x6600, "clock_read_retry")

    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_HI_OFFSET), 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET))
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_LO_OFFSET), 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET))

    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_GENERATION_OFFSET), 0)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_GENERATION_OFFSET), 1)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6600, "clock_read_retry")
    asm.andi_w(1, 0)
    asm.branch_word(0x6600, "clock_read_retry")

    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_HI_OFFSET), 0)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_CLOCK_READ_LO_OFFSET), 1)


def _emit_wait_until_due(asm: _Assembler68K) -> None:
    """Wait until stable clock D0:D1 is >= current record time D2:D3."""

    asm.move_dn_absw(2, _svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_HI_OFFSET))
    asm.move_dn_absw(3, _svc(SATURN_MIDI_68K_STREAM_NEXT_DUE_LO_OFFSET))
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
    asm.label("scheduler_wait")
    _emit_stable_clock_read(asm)

    # Compare unsigned 32-bit clock D0:D1 against due time D2:D3.
    asm.cmp_dn_w(2, 0)
    asm.branch_word(0x6500, "scheduler_wait")  # clock high < due high
    asm.branch_word(0x6200, "scheduler_due")   # clock high > due high
    asm.cmp_dn_w(3, 1)
    asm.branch_word(0x6500, "scheduler_wait")  # equal high; low still early
    asm.label("scheduler_due")
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_RUNNING, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))


def _emit_state_mutation_dispatch(asm: _Assembler68K) -> None:
    """Apply current D6/D4/D5/D7 event to the persistent state arrays."""

    _emit_channel_dispatch(asm)

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
    _emit_note_byte_address(asm, "stream_note_off")
    asm.bclr_dn_an_indirect(5, 3)
    _emit_active_count_decrement(asm, "stream_note_off_count_done")
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_op_note_on")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_VELOCITY), 1)
    asm.cmpi_w(0, 7)
    asm.branch_word(0x6700, "stream_note_on_zero_velocity")
    _emit_note_byte_address(asm, "stream_note_on")
    asm.bset_dn_an_indirect(5, 3)
    _emit_active_count_increment(asm, "stream_note_on_count_done")
    asm.branch_word(0x6000, "stream_record_done")

    asm.label("stream_note_on_zero_velocity")
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


def build_srk_saturn_midi_68k_resident_stream_service_image() -> SaturnMidi68KResidentStreamServiceImage:
    """Build the continuous state-preserving resident stream/scheduler image."""

    if SATURN_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS != 32:
        raise SaturnMidi68KResidentStreamServiceError("reviewed queue capacity changed")

    summary_words, controller_words, active_note_words = (
        build_srk_saturn_midi_68k_resident_state_initial_blocks()
    )
    asm = _Assembler68K()

    # Initialize persistent MIDI state exactly once at service boot.
    _emit_word_block(asm, SATURN_MIDI_68K_STATE_ADDRESS, summary_words)
    _emit_word_block(asm, SATURN_MIDI_68K_CONTROLLER_ADDRESS, controller_words)
    _emit_word_block(asm, SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, active_note_words)

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

    # Continuous producer/refill loop.
    asm.label("poll_batch")
    asm.move_imm_absw(SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH, _svc(SATURN_MIDI_68K_STREAM_FLAGS_OFFSET))
    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_word(0x6700, "poll_batch")

    # READY with the already-acknowledged sequence is simply the producer still
    # holding the previous batch; wait rather than processing it twice.
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_absw_to_dn(_MB_READ_SEQUENCE, 1)
    asm.cmp_dn_w(1, 0)
    asm.branch_word(0x6700, "poll_batch")

    # Enforce strict non-zero sequence continuity, wrapping FFFF -> 1.
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

    # Mailbox identity/capacity/count contract.
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

    # Validate the complete refill before any state mutation.  D0:D1 carries
    # the last executed timestamp across refill boundaries.
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_LAST_DUE_HI_OFFSET), 0)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_LAST_DUE_LO_OFFSET), 1)
    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)
    asm.label("validation_loop")
    _emit_record_byte_reads(asm)
    _emit_record_validation(asm)

    # Require event time D2:D3 >= previous accepted time D0:D1.
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

    # Batch is now fully accepted; reset per-batch progress and schedule it.
    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET))
    asm.move_imm_absw(0, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)

    asm.label("schedule_record")
    _emit_record_byte_reads(asm)
    _emit_wait_until_due(asm)
    _emit_state_mutation_dispatch(asm)

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

    # Increment 32-bit total processed count.
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

    # Acknowledge this refill only after every record reached its timestamp and
    # mutated state.
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_CURRENT_SEQUENCE_OFFSET))
    asm.move_dn_absw(4, _MB_READ_INDEX)
    asm.move_absw_to_dn(_svc(SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET), 0)
    asm.addq_w(1, 0)
    asm.move_dn_absw(0, _svc(SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET))
    asm.move_imm_absw(0, _MB_LAST_ERROR)
    asm.move_imm_absw(0, _svc(SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET))
    asm.move_imm_absw(1, _state_telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.branch_word(0x6000, "poll_batch")

    _emit_service_error(asm, "error_magic", SATURN_MIDI_68K_STREAM_ERROR_MAGIC)
    _emit_service_error(asm, "error_version", SATURN_MIDI_68K_STREAM_ERROR_VERSION)
    _emit_service_error(asm, "error_contract", SATURN_MIDI_68K_STREAM_ERROR_CONTRACT)
    _emit_service_error(asm, "error_empty", SATURN_MIDI_68K_STREAM_ERROR_EMPTY)
    _emit_service_error(asm, "error_count", SATURN_MIDI_68K_STREAM_ERROR_COUNT)
    _emit_service_error(asm, "error_record", SATURN_MIDI_68K_STREAM_ERROR_RECORD)
    _emit_service_error(asm, "error_sequence", SATURN_MIDI_68K_STREAM_ERROR_SEQUENCE)
    _emit_service_error(asm, "error_timestamp", SATURN_MIDI_68K_STREAM_ERROR_TIMESTAMP)

    image = SaturnMidi68KResidentStreamServiceImage(words=asm.finish())
    if image.end_address > SATURN_MIDI_68K_RESIDENT_STREAM_MAX_END:
        raise SaturnMidi68KResidentStreamServiceError(
            "resident stream service exceeds the reviewed 0x4000-0x8000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_resident_stream_service_header() -> str:
    """Render the inert C89 declaration for the continuous service image."""

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STREAM_SERVICE_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STREAM_SERVICE_H",
            "",
            "/* Continuous stream/scheduler image. This declaration does not install or run it. */",
            f"#define SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS {SATURN_MIDI_68K_RESIDENT_STREAM_MAX_RECORDS}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_resident_stream_service_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_stream_service_source() -> str:
    """Render the generated continuous service as inert C89 constant data."""

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    lines = [
        '#include "srk_saturn_midi_68k_resident_stream_service.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_resident_stream_service_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        row = image.words[index : index + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in row) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
