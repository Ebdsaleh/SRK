"""Phase-B silent SRKM v1 resident decoder with dynamic MIDI state mutation.

R20 physically accepted the content-independent runtime queue loop.  This new
image preserves R20 as an immutable anchor and advances the resident MC68EC000
from validation-only decoding to live command-state maintenance.

The generated program remains deliberately silent.  It validates the complete
runtime batch before touching state, initializes the reviewed state contract,
then applies all seven SRKM v1 opcode classes dynamically across all sixteen
channels.  It updates channel summaries, the complete 16x128 controller byte
matrix and the 16x128 active-note bitmap without touching SCSP registers.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_ACTIVE_NOTES_BYTES,
    SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL,
    SATURN_MIDI_68K_CHANNEL_COUNT,
    SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
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
    SATURN_MIDI_68K_CONTROLLER_COUNT,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
    default_saturn_midi_68k_channel_state,
    pack_srk_saturn_midi_68k_channel_words,
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


SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS = 0x00004000
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_END = 0x00008000
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS = SATURN_MIDI_QUEUE_CAPACITY

SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_MAGIC = 1
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_VERSION = 2
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_CONTRACT = 3
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_EMPTY = 4
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_COUNT = 6
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_RECORD = 7

SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC = 0x5253  # "RS"
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION = 1
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC_OFFSET = 0
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION_OFFSET = 2
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET = 4
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET = 6
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET = 8
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET = 10
SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET = 12

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


class SaturnMidi68KResidentStateDecoderError(RuntimeError):
    """Raised when the Phase-B resident state decoder cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStateDecoderImage:
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return len(self.words) * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


class _Assembler68K:
    """Word-oriented assembler for the reviewed Phase-B MC68000 subset."""

    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.word_branches: list[tuple[int, int, str]] = []

    def label(self, name: str) -> None:
        if name in self.labels:
            raise SaturnMidi68KResidentStateDecoderError(f"duplicate 68K label: {name}")
        self.labels[name] = len(self.words)

    def word(self, value: int) -> None:
        if value < 0 or value > 0xFFFF:
            raise SaturnMidi68KResidentStateDecoderError(f"68K word out of range: {value}")
        self.words.append(value)

    @staticmethod
    def _require_dn(register: int) -> None:
        if register < 0 or register > 7:
            raise SaturnMidi68KResidentStateDecoderError("invalid 68K data register")

    @staticmethod
    def _require_an(register: int) -> None:
        if register < 0 or register > 7:
            raise SaturnMidi68KResidentStateDecoderError("invalid 68K address register")

    @staticmethod
    def _require_absw(address: int) -> None:
        if address < 0 or address > 0x7FFF:
            raise SaturnMidi68KResidentStateDecoderError(
                f"absolute-short address must remain positive: 0x{address:08X}"
            )
        if address & 1:
            raise SaturnMidi68KResidentStateDecoderError(
                f"word access must remain even-aligned: 0x{address:08X}"
            )

    def move_absw_to_dn(self, address: int, data_register: int) -> None:
        self._require_absw(address)
        self._require_dn(data_register)
        self.word(0x3038 + (data_register << 9))
        self.word(address)

    def move_imm_to_dn(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        self.word(0x303C + (data_register << 9))
        self.word(immediate & 0xFFFF)

    def move_dn_to_dn(self, source_register: int, destination_register: int) -> None:
        self._require_dn(source_register)
        self._require_dn(destination_register)
        self.word(0x3000 + (destination_register << 9) + source_register)

    def move_postinc_a0_to_dn(self, data_register: int) -> None:
        self._require_dn(data_register)
        self.word(0x3018 + (data_register << 9))

    def move_b_postinc_a0_to_dn(self, data_register: int) -> None:
        self._require_dn(data_register)
        # MOVE.B (A0)+,Dn
        self.word(0x1018 + (data_register << 9))

    def lea_absw_an(self, address: int, address_register: int) -> None:
        self._require_absw(address)
        self._require_an(address_register)
        # LEA (xxx).W,An
        self.word(0x41F8 + (address_register << 9))
        self.word(address)

    def cmpi_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        self.word(0x0C40 + data_register)
        self.word(immediate & 0xFFFF)

    def andi_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        self.word(0x0240 + data_register)
        self.word(immediate & 0xFFFF)

    def addi_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        self.word(0x0640 + data_register)
        self.word(immediate & 0xFFFF)

    def cmp_dn_w(self, source_register: int, destination_register: int) -> None:
        self._require_dn(source_register)
        self._require_dn(destination_register)
        self.word(0xB040 + (destination_register << 9) + source_register)

    def addq_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        if immediate < 1 or immediate > 8:
            raise SaturnMidi68KResidentStateDecoderError("ADDQ immediate must be 1..8")
        encoded = immediate & 7
        self.word(0x5040 + (encoded << 9) + data_register)

    def subq_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        if immediate < 1 or immediate > 8:
            raise SaturnMidi68KResidentStateDecoderError("SUBQ immediate must be 1..8")
        encoded = immediate & 7
        self.word(0x5140 + (encoded << 9) + data_register)

    def add_w_dn_to_dn(self, source_register: int, destination_register: int) -> None:
        self._require_dn(source_register)
        self._require_dn(destination_register)
        # ADD.W Dn,Dm
        self.word(0xD040 + (destination_register << 9) + source_register)

    def move_imm_absw(self, immediate: int, address: int) -> None:
        self._require_absw(address)
        self.word(0x31FC)
        self.word(immediate & 0xFFFF)
        self.word(address)

    def move_dn_absw(self, data_register: int, address: int) -> None:
        self._require_dn(data_register)
        self._require_absw(address)
        self.word(0x31C0 + data_register)
        self.word(address)

    def move_d16_an_to_dn(
        self,
        address_register: int,
        displacement: int,
        data_register: int,
    ) -> None:
        self._require_an(address_register)
        self._require_dn(data_register)
        # MOVE.W d16(An),Dn
        self.word(0x3028 + address_register + (data_register << 9))
        self.word(displacement & 0xFFFF)

    def move_dn_d16_an(
        self,
        data_register: int,
        displacement: int,
        address_register: int,
    ) -> None:
        self._require_dn(data_register)
        self._require_an(address_register)
        # MOVE.W Dn,d16(An)
        self.word(0x3140 + (address_register << 9) + data_register)
        self.word(displacement & 0xFFFF)

    def adda_w_dn_an(self, data_register: int, address_register: int) -> None:
        self._require_dn(data_register)
        self._require_an(address_register)
        # ADDA.W Dn,An
        self.word(0xD0C0 + (address_register << 9) + data_register)

    def move_b_dn_an_indirect(self, data_register: int, address_register: int) -> None:
        self._require_dn(data_register)
        self._require_an(address_register)
        # MOVE.B Dn,(An)
        self.word(0x1080 + (address_register << 9) + data_register)

    def bset_dn_an_indirect(self, bit_register: int, address_register: int) -> None:
        self._require_dn(bit_register)
        self._require_an(address_register)
        # BSET Dn,(An) -- byte operation for a memory destination.
        self.word(0x01D0 + (bit_register << 9) + address_register)

    def bclr_dn_an_indirect(self, bit_register: int, address_register: int) -> None:
        self._require_dn(bit_register)
        self._require_an(address_register)
        # BCLR Dn,(An) -- byte operation for a memory destination.
        self.word(0x0190 + (bit_register << 9) + address_register)

    def branch_word(self, opcode: int, target: str) -> None:
        index = len(self.words)
        self.word(opcode & 0xFF00)
        self.word(0)
        self.word_branches.append((index, opcode & 0xFF00, target))

    def branch_short_self(self) -> None:
        self.word(0x60FE)

    def finish(self) -> tuple[int, ...]:
        words = list(self.words)
        for index, opcode, target_name in self.word_branches:
            try:
                target_index = self.labels[target_name]
            except KeyError as exc:
                raise SaturnMidi68KResidentStateDecoderError(
                    f"undefined 68K branch target: {target_name}"
                ) from exc
            displacement = (target_index - (index + 1)) * 2
            if displacement < -32768 or displacement > 32767:
                raise SaturnMidi68KResidentStateDecoderError(
                    f"68K word branch to {target_name} is out of range: {displacement}"
                )
            words[index] = opcode
            words[index + 1] = displacement & 0xFFFF
        return tuple(words)


def _telemetry(offset: int) -> int:
    return SATURN_MIDI_68K_TELEMETRY_ADDRESS + offset


def _state_displacement(word_index: int) -> int:
    return word_index * 2


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise SaturnMidi68KResidentStateDecoderError("state byte payload must be word aligned")
    return tuple(
        (payload[index] << 8) | payload[index + 1]
        for index in range(0, len(payload), 2)
    )


def build_srk_saturn_midi_68k_resident_state_initial_blocks() -> tuple[
    tuple[int, ...], tuple[int, ...], tuple[int, ...]
]:
    """Return deterministic summary/controller/note blocks written after validation."""

    default = default_saturn_midi_68k_channel_state()
    summary = tuple(
        word
        for _ in range(SATURN_MIDI_68K_CHANNEL_COUNT)
        for word in pack_srk_saturn_midi_68k_channel_words(default)
    )
    controllers = bytes(
        value
        for _ in range(SATURN_MIDI_68K_CHANNEL_COUNT)
        for value in default.controllers
    )
    active_notes = bytes(SATURN_MIDI_68K_ACTIVE_NOTES_BYTES)
    return summary, _bytes_to_words(controllers), _bytes_to_words(active_notes)


def _emit_word_block(asm: _Assembler68K, address: int, words: tuple[int, ...]) -> None:
    for index, value in enumerate(words):
        asm.move_imm_absw(value, address + index * 2)


def _emit_error(asm: _Assembler68K, label: str, error_code: int) -> None:
    asm.label(label)
    asm.move_imm_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET))
    asm.move_imm_absw(error_code, _MB_LAST_ERROR)
    asm.branch_short_self()


def _emit_record_byte_reads(asm: _Assembler68K) -> None:
    """Read one 8-byte record into D2,D3,D6,D4,D5,D7 and advance A0."""

    asm.move_postinc_a0_to_dn(2)  # timestamp high
    asm.move_postinc_a0_to_dn(3)  # timestamp low
    for register in (6, 4, 5, 7):
        asm.move_imm_to_dn(0, register)
        asm.move_b_postinc_a0_to_dn(register)


def _emit_record_validation(asm: _Assembler68K) -> None:
    # D6 opcode, D4 channel, D5 data0, D7 data1.
    for opcode in SaturnMidiOpcode:
        asm.cmpi_w(int(opcode), 6)
        asm.branch_word(0x6700, "validation_opcode_ok")
    asm.branch_word(0x6000, "error_record")
    asm.label("validation_opcode_ok")

    asm.cmpi_w(15, 4)
    asm.branch_word(0x6200, "error_record")  # BHI.W
    asm.cmpi_w(127, 5)
    asm.branch_word(0x6200, "error_record")
    asm.cmpi_w(127, 7)
    asm.branch_word(0x6200, "error_record")


def _emit_channel_dispatch(asm: _Assembler68K) -> None:
    for channel in range(SATURN_MIDI_68K_CHANNEL_COUNT):
        asm.cmpi_w(channel, 4)
        asm.branch_word(0x6700, f"channel_{channel}")
    asm.branch_word(0x6000, "error_record")

    for channel in range(SATURN_MIDI_68K_CHANNEL_COUNT):
        asm.label(f"channel_{channel}")
        asm.lea_absw_an(
            SATURN_MIDI_68K_STATE_ADDRESS
            + channel * SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
            1,
        )
        asm.lea_absw_an(
            SATURN_MIDI_68K_CONTROLLER_ADDRESS
            + channel * SATURN_MIDI_68K_CONTROLLER_COUNT,
            2,
        )
        asm.lea_absw_an(
            SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS
            + channel * SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL,
            3,
        )
        asm.branch_word(0x6000, "channel_ready")

    asm.label("channel_ready")


def _emit_note_byte_address(asm: _Assembler68K, prefix: str) -> None:
    # D5 starts as note 0..127. Preserve the note in the summary before this
    # helper is called; it reduces D5 to bit number 0..7 and puts byte offset
    # 0..15 in D4, then advances A3 to the selected bitmap byte.
    asm.move_imm_to_dn(0, 4)
    asm.label(f"{prefix}_byte_loop")
    asm.cmpi_w(8, 5)
    asm.branch_word(0x6500, f"{prefix}_byte_ready")  # BCS.W: D5 < 8
    asm.subq_w(8, 5)
    asm.addq_w(1, 4)
    asm.branch_word(0x6000, f"{prefix}_byte_loop")
    asm.label(f"{prefix}_byte_ready")
    asm.adda_w_dn_an(4, 3)


def _emit_active_count_increment(asm: _Assembler68K, skip_label: str) -> None:
    # BSET leaves Z=1 only when the bit was previously clear.
    asm.branch_word(0x6600, skip_label)  # BNE: already active
    asm.move_d16_an_to_dn(1, _state_displacement(SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT), 4)
    asm.addq_w(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT), 1)
    asm.label(skip_label)


def _emit_active_count_decrement(asm: _Assembler68K, skip_label: str) -> None:
    # BCLR leaves Z=1 when the bit was already clear.
    asm.branch_word(0x6700, skip_label)  # BEQ: no active note to remove
    asm.move_d16_an_to_dn(1, _state_displacement(SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT), 4)
    asm.subq_w(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT), 1)
    asm.label(skip_label)


def build_srk_saturn_midi_68k_resident_state_decoder_image() -> SaturnMidi68KResidentStateDecoderImage:
    """Build the Phase-B content-independent state-mutating resident decoder."""

    if SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS != 32:
        raise SaturnMidi68KResidentStateDecoderError("reviewed resident queue capacity changed")

    summary_words, controller_words, active_note_words = (
        build_srk_saturn_midi_68k_resident_state_initial_blocks()
    )

    asm = _Assembler68K()
    asm.label("poll")

    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_word(0x6700, "poll")

    # Publish Phase-B identity and withdraw stale public completion state.
    asm.move_imm_absw(
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC_OFFSET),
    )
    asm.move_imm_absw(
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION_OFFSET),
    )
    for offset in (
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET,
        SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET,
    ):
        asm.move_imm_absw(0, _telemetry(offset))
    asm.move_imm_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _MB_LAST_ERROR)

    # Mailbox contract.
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
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, "error_contract")
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, "error_empty")
    asm.cmpi_w(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS, 0)
    asm.branch_word(0x6200, "error_count")
    asm.move_absw_to_dn(_MB_WRITE_INDEX, 1)
    asm.cmp_dn_w(0, 1)
    asm.branch_word(0x6600, "error_count")

    # Pass one validates the entire runtime queue before any state mutation.
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.move_imm_to_dn(0, 1)
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)
    asm.label("validation_loop")
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET),
    )
    _emit_record_byte_reads(asm)
    _emit_record_validation(asm)
    asm.addq_w(1, 1)
    asm.subq_w(1, 0)
    asm.branch_word(0x6600, "validation_loop")

    # Atomic state publication boundary: reset deterministic state only after
    # the complete batch has validated.
    _emit_word_block(asm, SATURN_MIDI_68K_STATE_ADDRESS, summary_words)
    _emit_word_block(asm, SATURN_MIDI_68K_CONTROLLER_ADDRESS, controller_words)
    _emit_word_block(asm, SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, active_note_words)

    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET))
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET))

    # Pass two applies the validated records dynamically.
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.move_imm_to_dn(0, 1)
    asm.lea_absw_an(SATURN_MIDI_QUEUE_ADDRESS, 0)
    asm.label("mutation_loop")
    _emit_record_byte_reads(asm)
    _emit_channel_dispatch(asm)

    # Common per-channel event accounting.
    asm.move_d16_an_to_dn(1, _state_displacement(SATURN_MIDI_68K_CH_EVENT_COUNT), 4)
    asm.addq_w(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_EVENT_COUNT), 1)
    asm.move_dn_d16_an(6, _state_displacement(SATURN_MIDI_68K_CH_LAST_OPCODE), 1)

    for opcode, label in (
        (SaturnMidiOpcode.NOTE_OFF, "op_note_off"),
        (SaturnMidiOpcode.NOTE_ON, "op_note_on"),
        (SaturnMidiOpcode.POLY_AFTERTOUCH, "op_poly_aftertouch"),
        (SaturnMidiOpcode.CONTROL_CHANGE, "op_control_change"),
        (SaturnMidiOpcode.PROGRAM_CHANGE, "op_program_change"),
        (SaturnMidiOpcode.CHANNEL_PRESSURE, "op_channel_pressure"),
        (SaturnMidiOpcode.PITCH_BEND, "op_pitch_bend"),
    ):
        asm.cmpi_w(int(opcode), 6)
        asm.branch_word(0x6700, label)
    asm.branch_word(0x6000, "error_record")

    asm.label("op_note_off")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_VELOCITY), 1)
    _emit_note_byte_address(asm, "note_off")
    asm.bclr_dn_an_indirect(5, 3)
    _emit_active_count_decrement(asm, "note_off_count_done")
    asm.branch_word(0x6000, "record_done")

    asm.label("op_note_on")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_VELOCITY), 1)
    asm.cmpi_w(0, 7)
    asm.branch_word(0x6700, "note_on_zero_velocity")
    _emit_note_byte_address(asm, "note_on")
    asm.bset_dn_an_indirect(5, 3)
    _emit_active_count_increment(asm, "note_on_count_done")
    asm.branch_word(0x6000, "record_done")

    asm.label("note_on_zero_velocity")
    _emit_note_byte_address(asm, "note_on_zero")
    asm.bclr_dn_an_indirect(5, 3)
    _emit_active_count_decrement(asm, "note_on_zero_count_done")
    asm.branch_word(0x6000, "record_done")

    asm.label("op_poly_aftertouch")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_LAST_POLY_NOTE), 1)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE), 1)
    asm.branch_word(0x6000, "record_done")

    asm.label("op_control_change")
    asm.adda_w_dn_an(5, 2)
    asm.move_b_dn_an_indirect(7, 2)
    for controller, label in (
        (0, "cc_bank_msb"),
        (32, "cc_bank_lsb"),
        (7, "cc_volume"),
        (10, "cc_pan"),
        (11, "cc_expression"),
        (64, "cc_sustain"),
    ):
        asm.cmpi_w(controller, 5)
        asm.branch_word(0x6700, label)
    asm.branch_word(0x6000, "record_done")

    for label, field in (
        ("cc_bank_msb", SATURN_MIDI_68K_CH_BANK_MSB),
        ("cc_bank_lsb", SATURN_MIDI_68K_CH_BANK_LSB),
        ("cc_volume", SATURN_MIDI_68K_CH_VOLUME),
        ("cc_pan", SATURN_MIDI_68K_CH_PAN),
        ("cc_expression", SATURN_MIDI_68K_CH_EXPRESSION),
    ):
        asm.label(label)
        asm.move_dn_d16_an(7, _state_displacement(field), 1)
        asm.branch_word(0x6000, "record_done")

    asm.label("cc_sustain")
    asm.cmpi_w(64, 7)
    asm.branch_word(0x6500, "cc_sustain_off")
    asm.move_imm_to_dn(1, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_SUSTAIN), 1)
    asm.branch_word(0x6000, "record_done")
    asm.label("cc_sustain_off")
    asm.move_imm_to_dn(0, 4)
    asm.move_dn_d16_an(4, _state_displacement(SATURN_MIDI_68K_CH_SUSTAIN), 1)
    asm.branch_word(0x6000, "record_done")

    asm.label("op_program_change")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_PROGRAM), 1)
    asm.branch_word(0x6000, "record_done")

    asm.label("op_channel_pressure")
    asm.move_dn_d16_an(5, _state_displacement(SATURN_MIDI_68K_CH_CHANNEL_PRESSURE), 1)
    asm.branch_word(0x6000, "record_done")

    asm.label("op_pitch_bend")
    for _ in range(7):
        asm.add_w_dn_to_dn(7, 7)
    asm.add_w_dn_to_dn(5, 7)
    asm.move_dn_d16_an(7, _state_displacement(SATURN_MIDI_68K_CH_PITCH_BEND), 1)
    asm.branch_word(0x6000, "record_done")

    asm.label("record_done")
    asm.addq_w(1, 1)
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_PROCESSED_OFFSET),
    )
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET),
    )
    asm.move_dn_absw(
        2,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET),
    )
    asm.move_dn_absw(
        3,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET),
    )
    asm.subq_w(1, 0)
    asm.branch_word(0x6600, "mutation_loop")

    asm.move_imm_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_READY_OFFSET),
    )
    asm.move_dn_absw(1, _MB_READ_INDEX)
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_LAST_ERROR)
    asm.branch_short_self()

    _emit_error(asm, "error_magic", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_MAGIC)
    _emit_error(asm, "error_version", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_VERSION)
    _emit_error(asm, "error_contract", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_CONTRACT)
    _emit_error(asm, "error_empty", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_EMPTY)
    _emit_error(asm, "error_count", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_COUNT)
    _emit_error(asm, "error_record", SATURN_MIDI_68K_RESIDENT_STATE_DECODER_ERROR_RECORD)

    image = SaturnMidi68KResidentStateDecoderImage(words=asm.finish())
    if image.end_address > SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_END:
        raise SaturnMidi68KResidentStateDecoderError(
            "resident state decoder image exceeds the reviewed 0x4000-0x8000 envelope"
        )
    return image


def render_srk_saturn_midi_68k_resident_state_decoder_header() -> str:
    """Render the inert C89 declaration for the Phase-B image."""

    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_H",
            "",
            "/* Phase-B state decoder. This declaration does not install or run it. */",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_STACK_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_STATE_DECODER_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS {SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC 0x{SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION {SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_resident_state_decoder_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_state_decoder_source() -> str:
    """Render the generated Phase-B image as inert C89 constant data."""

    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    lines = [
        '#include "srk_saturn_midi_68k_resident_state_decoder.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_resident_state_decoder_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        row = image.words[index : index + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in row) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
