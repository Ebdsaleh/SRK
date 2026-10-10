"""Protocol-only MC68EC000 consumer image for the Saturn MIDI diagnostic.

This module defines a tiny deterministic 68000 program that only validates the
SRK MIDI mailbox, reads the first queued record and acknowledges it.  It does
not touch SCSP registers or generate audio.  Nothing in production launches the
program yet.

The instruction image is generated from a deliberately tiny reviewed subset of
MC68000 encodings so every word and short branch displacement is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_CAPACITY,
)
from .midi_mailbox import (
    SATURN_MIDI_MAILBOX_FLAG_READY,
    SATURN_MIDI_MAILBOX_WORD_COUNT,
    build_srk_saturn_midi_preload_image,
)


SATURN_MIDI_68K_PROGRAM_ADDRESS = 0x00000600
SATURN_MIDI_68K_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_FIRST_RECORD_WORDS = (0x0000, 0x0000, 0x0400, 0x0000)

SATURN_MIDI_68K_ERROR_MAGIC = 1
SATURN_MIDI_68K_ERROR_VERSION = 2
SATURN_MIDI_68K_ERROR_CONTRACT = 3
SATURN_MIDI_68K_ERROR_EMPTY = 4
SATURN_MIDI_68K_ERROR_RECORD = 5

_MB_MAGIC0 = SATURN_MIDI_MAILBOX_ADDRESS + 0
_MB_MAGIC1 = SATURN_MIDI_MAILBOX_ADDRESS + 2
_MB_VERSION = SATURN_MIDI_MAILBOX_ADDRESS + 4
_MB_FLAGS = SATURN_MIDI_MAILBOX_ADDRESS + 6
_MB_WRITE_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 8
_MB_READ_SEQUENCE = SATURN_MIDI_MAILBOX_ADDRESS + 10
_MB_READ_INDEX = SATURN_MIDI_MAILBOX_ADDRESS + 14
_MB_QUEUE_CAPACITY = SATURN_MIDI_MAILBOX_ADDRESS + 16
_MB_QUEUE_COUNT = SATURN_MIDI_MAILBOX_ADDRESS + 18
_MB_LAST_ERROR = SATURN_MIDI_MAILBOX_ADDRESS + 20


class SaturnMidi68KConsumerError(RuntimeError):
    """Raised when the protocol-only consumer image cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KConsumerImage:
    words: tuple[int, ...]

    @property
    def byte_size(self) -> int:
        return len(self.words) * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


@dataclass(frozen=True)
class SaturnMidi68KProtocolResult:
    status: str
    error_code: int
    mailbox_words: tuple[int, ...]


class _Assembler68K:
    """Minimal word-oriented assembler for the reviewed proof-program subset."""

    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.branches: list[tuple[int, int, str]] = []

    def label(self, name: str) -> None:
        if name in self.labels:
            raise SaturnMidi68KConsumerError(f"duplicate 68K label: {name}")
        self.labels[name] = len(self.words)

    def word(self, value: int) -> None:
        if value < 0 or value > 0xFFFF:
            raise SaturnMidi68KConsumerError(f"68K word out of range: {value}")
        self.words.append(value)

    def move_absw_to_dn(self, address: int, data_register: int) -> None:
        if address < 0 or address > 0x7FFF:
            raise SaturnMidi68KConsumerError(
                f"absolute-short address must remain positive: 0x{address:08X}"
            )
        if data_register < 0 or data_register > 7:
            raise SaturnMidi68KConsumerError("invalid 68K data register")
        # MOVE.W (xxx).W,Dn
        self.word(0x3038 + (data_register << 9))
        self.word(address)

    def cmpi_w(self, immediate: int, data_register: int) -> None:
        # CMPI.W #imm,Dn
        self.word(0x0C40 + data_register)
        self.word(immediate & 0xFFFF)

    def andi_w(self, immediate: int, data_register: int) -> None:
        # ANDI.W #imm,Dn
        self.word(0x0240 + data_register)
        self.word(immediate & 0xFFFF)

    def move_imm_absw(self, immediate: int, address: int) -> None:
        # MOVE.W #imm,(xxx).W
        self.word(0x31FC)
        self.word(immediate & 0xFFFF)
        self.word(address)

    def move_dn_absw(self, data_register: int, address: int) -> None:
        # MOVE.W Dn,(xxx).W
        self.word(0x31C0 + data_register)
        self.word(address)

    def branch_short(self, opcode: int, target: str) -> None:
        index = len(self.words)
        self.word(opcode & 0xFF00)
        self.branches.append((index, opcode & 0xFF00, target))

    def finish(self) -> tuple[int, ...]:
        words = list(self.words)
        for index, opcode, target_name in self.branches:
            try:
                target_index = self.labels[target_name]
            except KeyError as exc:
                raise SaturnMidi68KConsumerError(
                    f"undefined 68K branch target: {target_name}"
                ) from exc
            displacement = (target_index - (index + 1)) * 2
            if displacement == 0 or displacement < -128 or displacement > 127:
                raise SaturnMidi68KConsumerError(
                    f"68K short branch to {target_name} is out of range: {displacement}"
                )
            words[index] = opcode | (displacement & 0xFF)
        return tuple(words)


def build_srk_saturn_midi_68k_consumer_image() -> SaturnMidi68KConsumerImage:
    """Build the deterministic protocol-only MC68EC000 consumer machine code."""

    canonical = build_srk_saturn_midi_preload_image()
    if canonical.queue_words[:4] != SATURN_MIDI_68K_FIRST_RECORD_WORDS:
        raise SaturnMidi68KConsumerError(
            "canonical first MIDI queue record no longer matches the 68K proof contract"
        )

    asm = _Assembler68K()
    asm.label("poll")

    # Wait until the SH-2 producer publishes READY.
    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_short(0x6700, "poll")  # BEQ.S

    # Validate mailbox identity and bounded queue contract.
    asm.move_absw_to_dn(_MB_MAGIC0, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_MAGIC0, 0)
    asm.branch_short(0x6600, "error_magic")  # BNE.S

    asm.move_absw_to_dn(_MB_MAGIC1, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_MAGIC1, 0)
    asm.branch_short(0x6600, "error_magic")

    asm.move_absw_to_dn(_MB_VERSION, 0)
    asm.cmpi_w(SATURN_MIDI_MAILBOX_VERSION, 0)
    asm.branch_short(0x6600, "error_version")

    asm.move_absw_to_dn(_MB_QUEUE_CAPACITY, 0)
    asm.cmpi_w(SATURN_MIDI_QUEUE_CAPACITY, 0)
    asm.branch_short(0x6600, "error_contract")

    asm.move_absw_to_dn(_MB_QUEUE_COUNT, 0)
    asm.cmpi_w(0, 0)
    asm.branch_short(0x6700, "error_empty")

    # Read and validate every word of the canonical first SRKM record.
    for data_register, (offset, expected) in enumerate(
        zip((0, 2, 4, 6), SATURN_MIDI_68K_FIRST_RECORD_WORDS)
    ):
        asm.move_absw_to_dn(SATURN_MIDI_QUEUE_ADDRESS + offset, data_register)
        asm.cmpi_w(expected, data_register)
        asm.branch_short(0x6600, "error_record")

    # Acknowledge exactly one consumed record.  Copy the producer's write
    # sequence into read-sequence only after the record checks succeed.
    asm.move_imm_absw(1, _MB_READ_INDEX)
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_LAST_ERROR)

    asm.label("success_hold")
    asm.branch_short(0x6000, "success_hold")  # BRA.S

    asm.label("error_magic")
    asm.move_imm_absw(SATURN_MIDI_68K_ERROR_MAGIC, _MB_LAST_ERROR)
    asm.branch_short(0x6000, "error_hold")

    asm.label("error_version")
    asm.move_imm_absw(SATURN_MIDI_68K_ERROR_VERSION, _MB_LAST_ERROR)
    asm.branch_short(0x6000, "error_hold")

    asm.label("error_contract")
    asm.move_imm_absw(SATURN_MIDI_68K_ERROR_CONTRACT, _MB_LAST_ERROR)
    asm.branch_short(0x6000, "error_hold")

    asm.label("error_empty")
    asm.move_imm_absw(SATURN_MIDI_68K_ERROR_EMPTY, _MB_LAST_ERROR)
    asm.branch_short(0x6000, "error_hold")

    asm.label("error_record")
    asm.move_imm_absw(SATURN_MIDI_68K_ERROR_RECORD, _MB_LAST_ERROR)

    asm.label("error_hold")
    asm.branch_short(0x6000, "error_hold")

    image = SaturnMidi68KConsumerImage(words=asm.finish())
    if image.end_address > SATURN_MIDI_MAILBOX_ADDRESS:
        raise SaturnMidi68KConsumerError(
            "68K proof program overlaps the MIDI mailbox region"
        )
    return image


def simulate_srk_saturn_midi_68k_protocol(
    mailbox_words: tuple[int, ...],
    queue_words: tuple[int, ...],
) -> SaturnMidi68KProtocolResult:
    """Model the proof consumer's externally visible mailbox semantics."""

    if len(mailbox_words) != SATURN_MIDI_MAILBOX_WORD_COUNT:
        raise SaturnMidi68KConsumerError("mailbox model requires exactly 12 words")

    output = list(mailbox_words)
    if (output[3] & SATURN_MIDI_MAILBOX_FLAG_READY) == 0:
        return SaturnMidi68KProtocolResult("waiting", 0, tuple(output))

    def fail(code: int, status: str) -> SaturnMidi68KProtocolResult:
        output[10] = code
        return SaturnMidi68KProtocolResult(status, code, tuple(output))

    if output[0] != SATURN_MIDI_MAILBOX_MAGIC0 or output[1] != SATURN_MIDI_MAILBOX_MAGIC1:
        return fail(SATURN_MIDI_68K_ERROR_MAGIC, "error-magic")
    if output[2] != SATURN_MIDI_MAILBOX_VERSION:
        return fail(SATURN_MIDI_68K_ERROR_VERSION, "error-version")
    if output[8] != SATURN_MIDI_QUEUE_CAPACITY:
        return fail(SATURN_MIDI_68K_ERROR_CONTRACT, "error-contract")
    if output[9] == 0:
        return fail(SATURN_MIDI_68K_ERROR_EMPTY, "error-empty")
    if len(queue_words) < 4 or tuple(queue_words[:4]) != SATURN_MIDI_68K_FIRST_RECORD_WORDS:
        return fail(SATURN_MIDI_68K_ERROR_RECORD, "error-record")

    output[7] = 1
    output[5] = output[4]
    output[10] = 0
    return SaturnMidi68KProtocolResult("acknowledged", 0, tuple(output))


def render_srk_saturn_midi_68k_header() -> str:
    image = build_srk_saturn_midi_68k_consumer_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_PROGRAM_H",
            "#define SRK_SATURN_MIDI_68K_PROGRAM_H",
            "",
            "/* Protocol-only MC68EC000 program image. Not launched by this file. */",
            f"#define SRK_MIDI_68K_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_STACK_ADDRESS 0x{SATURN_MIDI_68K_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_PROGRAM_WORD_COUNT {len(image.words)}u",
            f"#define SRK_MIDI_68K_PROGRAM_BYTE_SIZE {image.byte_size}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_program[SRK_MIDI_68K_PROGRAM_WORD_COUNT];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_source() -> str:
    image = build_srk_saturn_midi_68k_consumer_image()
    lines = [
        '#include "srk_saturn_midi_68k_program.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_program[SRK_MIDI_68K_PROGRAM_WORD_COUNT] = {",
    ]
    for offset in range(0, len(image.words), 8):
        chunk = image.words[offset : offset + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
