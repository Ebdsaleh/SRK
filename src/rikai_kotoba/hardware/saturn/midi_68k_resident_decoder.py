"""General silent SRKM v1 resident decoder core for the Saturn MC68EC000.

R19 physically proved the complete canonical 27-record batch using an
intentionally unrolled consumer.  This module isolates the next architectural
risk: runtime loop control and pointer-driven queue traversal.

The generated MC68000 program is deliberately still silent.  It:

* waits for the SH-2 producer READY flag;
* validates mailbox identity, queue capacity, count/index agreement and a
  non-zero write sequence;
* accepts any 1..32-record SRKM v1 batch rather than one canonical payload;
* walks four words per record through A0 post-increment addressing;
* validates opcode, channel and both MIDI data bytes from the record itself;
* publishes bounded decoder telemetry as each record is accepted;
* acknowledges the actual runtime record count only after the complete batch;
* never mutates the command-state area and never touches SCSP registers.

This is Phase A of the post-R19 general resident decoder.  Dynamic MIDI state
mutation, streaming/refill, timing and SCSP voice work remain separate gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_command_engine import SATURN_MIDI_68K_TELEMETRY_ADDRESS
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


SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS = 0x00004000
SATURN_MIDI_68K_RESIDENT_DECODER_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_RESIDENT_DECODER_MAX_END = 0x00005000
SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS = SATURN_MIDI_QUEUE_CAPACITY

SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_MAGIC = 1
SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_VERSION = 2
SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_CONTRACT = 3
SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_EMPTY = 4
SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_COUNT = 6
SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD = 7

SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC = 0x5244  # "RD"
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION = 1
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC_OFFSET = 0
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION_OFFSET = 2
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_PROCESSED_OFFSET = 4
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET = 6
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET = 8
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET = 10
SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET = 12

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


class SaturnMidi68KResidentDecoderError(RuntimeError):
    """Raised when the silent resident decoder image cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderImage:
    words: tuple[int, ...]

    @property
    def word_count(self) -> int:
        return len(self.words)

    @property
    def byte_size(self) -> int:
        return len(self.words) * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


class _Assembler68K:
    """Word-oriented assembler for the deliberately small reviewed subset."""

    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.word_branches: list[tuple[int, int, str]] = []

    def label(self, name: str) -> None:
        if name in self.labels:
            raise SaturnMidi68KResidentDecoderError(f"duplicate 68K label: {name}")
        self.labels[name] = len(self.words)

    def word(self, value: int) -> None:
        if value < 0 or value > 0xFFFF:
            raise SaturnMidi68KResidentDecoderError(f"68K word out of range: {value}")
        self.words.append(value)

    @staticmethod
    def _require_dn(register: int) -> None:
        if register < 0 or register > 7:
            raise SaturnMidi68KResidentDecoderError("invalid 68K data register")

    @staticmethod
    def _require_absw(address: int) -> None:
        if address < 0 or address > 0x7FFF:
            raise SaturnMidi68KResidentDecoderError(
                f"absolute-short address must remain positive: 0x{address:08X}"
            )
        if address & 1:
            raise SaturnMidi68KResidentDecoderError(
                f"word access must remain even-aligned: 0x{address:08X}"
            )

    def move_absw_to_dn(self, address: int, data_register: int) -> None:
        self._require_absw(address)
        self._require_dn(data_register)
        # MOVE.W (xxx).W,Dn
        self.word(0x3038 + (data_register << 9))
        self.word(address)

    def move_imm_to_dn(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        # MOVE.W #imm,Dn
        self.word(0x303C + (data_register << 9))
        self.word(immediate & 0xFFFF)

    def move_dn_to_dn(self, source_register: int, destination_register: int) -> None:
        self._require_dn(source_register)
        self._require_dn(destination_register)
        # MOVE.W Dn,Dm
        self.word(0x3000 + (destination_register << 9) + source_register)

    def move_postinc_a0_to_dn(self, data_register: int) -> None:
        self._require_dn(data_register)
        # MOVE.W (A0)+,Dn
        self.word(0x3018 + (data_register << 9))

    def lea_absw_a0(self, address: int) -> None:
        self._require_absw(address)
        # LEA (xxx).W,A0
        self.word(0x41F8)
        self.word(address)

    def cmpi_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        # CMPI.W #imm,Dn
        self.word(0x0C40 + data_register)
        self.word(immediate & 0xFFFF)

    def cmp_dn_w(self, source_register: int, destination_register: int) -> None:
        self._require_dn(source_register)
        self._require_dn(destination_register)
        # CMP.W Dn,Dm -- destination minus source, flags only.
        self.word(0xB040 + (destination_register << 9) + source_register)

    def andi_w(self, immediate: int, data_register: int) -> None:
        self._require_dn(data_register)
        # ANDI.W #imm,Dn
        self.word(0x0240 + data_register)
        self.word(immediate & 0xFFFF)

    def addq_w_one(self, data_register: int) -> None:
        self._require_dn(data_register)
        # ADDQ.W #1,Dn
        self.word(0x5240 + data_register)

    def subq_w_one(self, data_register: int) -> None:
        self._require_dn(data_register)
        # SUBQ.W #1,Dn
        self.word(0x5340 + data_register)

    def move_imm_absw(self, immediate: int, address: int) -> None:
        self._require_absw(address)
        # MOVE.W #imm,(xxx).W
        self.word(0x31FC)
        self.word(immediate & 0xFFFF)
        self.word(address)

    def move_dn_absw(self, data_register: int, address: int) -> None:
        self._require_dn(data_register)
        self._require_absw(address)
        # MOVE.W Dn,(xxx).W
        self.word(0x31C0 + data_register)
        self.word(address)

    def branch_word(self, opcode: int, target: str) -> None:
        index = len(self.words)
        self.word(opcode & 0xFF00)
        self.word(0)
        self.word_branches.append((index, opcode & 0xFF00, target))

    def branch_short_self(self) -> None:
        # BRA.S -2
        self.word(0x60FE)

    def finish(self) -> tuple[int, ...]:
        words = list(self.words)
        for index, opcode, target_name in self.word_branches:
            try:
                target_index = self.labels[target_name]
            except KeyError as exc:
                raise SaturnMidi68KResidentDecoderError(
                    f"undefined 68K branch target: {target_name}"
                ) from exc
            displacement = (target_index - (index + 1)) * 2
            if displacement < -32768 or displacement > 32767:
                raise SaturnMidi68KResidentDecoderError(
                    f"68K word branch to {target_name} is out of range: {displacement}"
                )
            words[index] = opcode
            words[index + 1] = displacement & 0xFFFF
        return tuple(words)


def _telemetry(offset: int) -> int:
    return SATURN_MIDI_68K_TELEMETRY_ADDRESS + offset


def _emit_error(asm: _Assembler68K, label: str, error_code: int) -> None:
    asm.label(label)
    asm.move_imm_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET))
    asm.move_imm_absw(error_code, _MB_LAST_ERROR)
    asm.branch_short_self()


def build_srk_saturn_midi_68k_resident_decoder_image() -> SaturnMidi68KResidentDecoderImage:
    """Build the content-independent silent resident decoder core image."""

    if SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS != 32:
        raise SaturnMidi68KResidentDecoderError("reviewed resident queue capacity changed")

    asm = _Assembler68K()
    asm.label("poll")

    # READY is the SH-2 publication barrier.  No queue word is read before it.
    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_word(0x6700, "poll")  # BEQ.W

    # Publish decoder identity and withdraw any stale acknowledgement before
    # validating the newly published batch.
    asm.move_imm_absw(
        SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC_OFFSET),
    )
    asm.move_imm_absw(
        SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION_OFFSET),
    )
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_PROCESSED_OFFSET))
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET))
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET))
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET))
    asm.move_imm_absw(0, _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET))
    asm.move_imm_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_READ_INDEX)
    asm.move_imm_absw(0, _MB_LAST_ERROR)

    asm.move_absw_to_dn(_MB_MAGIC0, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_MAGIC0, 0)
    asm.branch_word(0x6600, "error_magic")  # BNE.W

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

    # Runtime count is bounded but no longer tied to the canonical 27 records.
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.cmpi_w(0, 0)
    asm.branch_word(0x6700, "error_empty")
    asm.cmpi_w(SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS, 0)
    asm.branch_word(0x6200, "error_count")  # BHI.W -- unsigned count > capacity

    asm.move_absw_to_dn(_MB_WRITE_INDEX, 1)
    asm.cmp_dn_w(0, 1)
    asm.branch_word(0x6600, "error_count")

    # D0 = remaining records, D1 = processed/current index, A0 = queue pointer.
    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.move_imm_to_dn(0, 1)
    asm.lea_absw_a0(SATURN_MIDI_QUEUE_ADDRESS)

    asm.label("record_loop")
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET),
    )

    # Four big-endian Sound-RAM words per SRKM record.
    asm.move_postinc_a0_to_dn(2)  # timestamp high
    asm.move_postinc_a0_to_dn(3)  # timestamp low
    asm.move_postinc_a0_to_dn(4)  # opcode / channel
    asm.move_postinc_a0_to_dn(5)  # data0 / data1

    # Validate channel low byte <= 15 while preserving opcode in D6.
    asm.move_dn_to_dn(4, 6)
    asm.andi_w(0x00FF, 4)
    asm.cmpi_w(0x000F, 4)
    asm.branch_word(0x6200, "error_record")

    # Validate opcode high byte against the complete SRKM v1 opcode set.
    asm.andi_w(0xFF00, 6)
    for opcode in SaturnMidiOpcode:
        asm.cmpi_w(int(opcode) << 8, 6)
        asm.branch_word(0x6700, "opcode_ok")
    asm.branch_word(0x6000, "error_record")

    asm.label("opcode_ok")

    # Both packed MIDI data bytes are 7-bit.  A single mask catches either
    # high bit without needing byte-sized operations.
    asm.andi_w(0x8080, 5)
    asm.branch_word(0x6600, "error_record")

    # Record accepted: publish dynamic progress and the last decoded timestamp.
    asm.addq_w_one(1)
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_PROCESSED_OFFSET),
    )
    asm.move_dn_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_CURRENT_RECORD_OFFSET),
    )
    asm.move_dn_absw(
        2,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_HI_OFFSET),
    )
    asm.move_dn_absw(
        3,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_FINAL_TIME_LO_OFFSET),
    )

    asm.subq_w_one(0)
    asm.branch_word(0x6600, "record_loop")

    # Publish decoder-complete before the public mailbox acknowledgement.
    asm.move_imm_absw(
        1,
        _telemetry(SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_READY_OFFSET),
    )
    asm.move_dn_absw(1, _MB_READ_INDEX)
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_LAST_ERROR)
    asm.branch_short_self()

    _emit_error(asm, "error_magic", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_MAGIC)
    _emit_error(asm, "error_version", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_VERSION)
    _emit_error(asm, "error_contract", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_CONTRACT)
    _emit_error(asm, "error_empty", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_EMPTY)
    _emit_error(asm, "error_count", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_COUNT)
    _emit_error(asm, "error_record", SATURN_MIDI_68K_RESIDENT_DECODER_ERROR_RECORD)

    image = SaturnMidi68KResidentDecoderImage(words=asm.finish())
    if image.end_address > SATURN_MIDI_68K_RESIDENT_DECODER_MAX_END:
        raise SaturnMidi68KResidentDecoderError(
            "resident decoder image exceeds the reviewed program envelope"
        )
    return image


def render_srk_saturn_midi_68k_resident_decoder_header() -> str:
    """Render the inert C89 declaration for the generated decoder image."""

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_DECODER_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_DECODER_H",
            "",
            "/* Silent post-R19 decoder core. This declaration does not install or run it. */",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_STACK_ADDRESS 0x{SATURN_MIDI_68K_RESIDENT_DECODER_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROGRAM_WORD_COUNT {image.word_count}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS {SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC 0x{SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION {SATURN_MIDI_68K_RESIDENT_DECODER_TELEMETRY_VERSION}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_resident_decoder_program[];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_decoder_source() -> str:
    """Render the content-independent machine image as a C89 word array."""

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    lines = [
        '#include "srk_saturn_midi_68k_resident_decoder.h"',
        "",
        "/* Generated constant only: no Sound-RAM, SMPC or SCSP access occurs here. */",
        "const unsigned short srk_saturn_midi_68k_resident_decoder_program[] = {",
    ]
    for index in range(0, len(image.words), 8):
        chunk = image.words[index : index + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
