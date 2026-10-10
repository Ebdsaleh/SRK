"""Deterministic silent full-batch MC68EC000 consumer image.

R18 physically proved the SH-2 -> Sound RAM -> resident MC68EC000 mailbox
round trip.  The next hardware step must remain silent while proving that the
resident sound CPU can validate the complete canonical 27-record SRKM batch
and publish the reviewed command-engine state.

This module therefore generates an intentionally conservative MC68000 program:

* wait for READY;
* validate mailbox identity and the exact bounded batch contract;
* validate every 16-bit word of every canonical queue record;
* publish the model-derived channel/controller/note state below 0x2000;
* acknowledge all 27 records only after every validation and state write;
* never touch SCSP registers or generate audio.

The program is deliberately unrolled.  That makes the first post-R18 physical
image larger, but avoids introducing indexed addressing, loop counters or a
second set of unproven instruction encodings at the same time as the expanded
protocol proof.  A later tranche can replace the exact-batch validator with a
general resident decoder after this boundary is physically accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
    simulate_srk_saturn_midi_68k_command_engine,
)
from .midi_bridge import (
    SATURN_MIDI_MAILBOX_ADDRESS,
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_CAPACITY,
    build_srk_saturn_midi_bridge_assets,
)
from .midi_mailbox import (
    SATURN_MIDI_MAILBOX_FLAG_READY,
    SATURN_MIDI_MAILBOX_WORD_COUNT,
    build_srk_saturn_midi_preload_image,
)


SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS = 0x00004000
SATURN_MIDI_68K_SILENT_BATCH_STACK_ADDRESS = 0x0007FFF0
SATURN_MIDI_68K_SILENT_BATCH_MAX_END = 0x00008000
SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS = 27

SATURN_MIDI_68K_SILENT_BATCH_ERROR_MAGIC = 1
SATURN_MIDI_68K_SILENT_BATCH_ERROR_VERSION = 2
SATURN_MIDI_68K_SILENT_BATCH_ERROR_CONTRACT = 3
SATURN_MIDI_68K_SILENT_BATCH_ERROR_EMPTY = 4
SATURN_MIDI_68K_SILENT_BATCH_ERROR_COUNT = 6
SATURN_MIDI_68K_SILENT_BATCH_ERROR_RECORD = 7

SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC = 0x5342  # "SB"
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION = 1
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC_OFFSET = 0
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION_OFFSET = 2
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET = 4
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET = 6
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_HI_OFFSET = 8
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_LO_OFFSET = 10
SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET = 12

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


class SaturnMidi68KSilentBatchConsumerError(RuntimeError):
    """Raised when the silent full-batch image cannot be generated safely."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchConsumerImage:
    words: tuple[int, ...]
    queue_word_count: int
    expected_records: int

    @property
    def byte_size(self) -> int:
        return len(self.words) * 2

    @property
    def end_address(self) -> int:
        return SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS + self.byte_size

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.words)
        return sha256(payload).hexdigest()


class _Assembler68K:
    """Minimal word-oriented assembler for the reviewed silent-batch subset."""

    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.word_branches: list[tuple[int, int, str]] = []

    def label(self, name: str) -> None:
        if name in self.labels:
            raise SaturnMidi68KSilentBatchConsumerError(f"duplicate 68K label: {name}")
        self.labels[name] = len(self.words)

    def word(self, value: int) -> None:
        if value < 0 or value > 0xFFFF:
            raise SaturnMidi68KSilentBatchConsumerError(f"68K word out of range: {value}")
        self.words.append(value)

    @staticmethod
    def _require_absw(address: int) -> None:
        if address < 0 or address > 0x7FFF:
            raise SaturnMidi68KSilentBatchConsumerError(
                f"absolute-short address must remain positive: 0x{address:08X}"
            )
        if address & 1:
            raise SaturnMidi68KSilentBatchConsumerError(
                f"word access must remain even-aligned: 0x{address:08X}"
            )

    def move_absw_to_dn(self, address: int, data_register: int) -> None:
        self._require_absw(address)
        if data_register < 0 or data_register > 7:
            raise SaturnMidi68KSilentBatchConsumerError("invalid 68K data register")
        # MOVE.W (xxx).W,Dn
        self.word(0x3038 + (data_register << 9))
        self.word(address)

    def cmpi_w(self, immediate: int, data_register: int) -> None:
        if data_register < 0 or data_register > 7:
            raise SaturnMidi68KSilentBatchConsumerError("invalid 68K data register")
        # CMPI.W #imm,Dn
        self.word(0x0C40 + data_register)
        self.word(immediate & 0xFFFF)

    def andi_w(self, immediate: int, data_register: int) -> None:
        if data_register < 0 or data_register > 7:
            raise SaturnMidi68KSilentBatchConsumerError("invalid 68K data register")
        # ANDI.W #imm,Dn
        self.word(0x0240 + data_register)
        self.word(immediate & 0xFFFF)

    def move_imm_absw(self, immediate: int, address: int) -> None:
        self._require_absw(address)
        # MOVE.W #imm,(xxx).W
        self.word(0x31FC)
        self.word(immediate & 0xFFFF)
        self.word(address)

    def move_dn_absw(self, data_register: int, address: int) -> None:
        self._require_absw(address)
        if data_register < 0 or data_register > 7:
            raise SaturnMidi68KSilentBatchConsumerError("invalid 68K data register")
        # MOVE.W Dn,(xxx).W
        self.word(0x31C0 + data_register)
        self.word(address)

    def branch_word(self, opcode: int, target: str) -> None:
        # Bcc.W/BRA.W.  A zero 8-bit displacement selects the following signed
        # 16-bit displacement word on the MC68000 family.
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
                raise SaturnMidi68KSilentBatchConsumerError(
                    f"undefined 68K branch target: {target_name}"
                ) from exc
            # Motorola Bcc uses PC = address of the branch instruction + 2.
            displacement = (target_index - (index + 1)) * 2
            if displacement < -32768 or displacement > 32767:
                raise SaturnMidi68KSilentBatchConsumerError(
                    f"68K word branch to {target_name} is out of range: {displacement}"
                )
            words[index] = opcode
            words[index + 1] = displacement & 0xFFFF
        return tuple(words)


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise SaturnMidi68KSilentBatchConsumerError("state payload must be word aligned")
    return tuple((payload[index] << 8) | payload[index + 1] for index in range(0, len(payload), 2))


def _emit_word_block(asm: _Assembler68K, address: int, words: tuple[int, ...]) -> None:
    for index, value in enumerate(words):
        asm.move_imm_absw(value, address + index * 2)


def build_srk_saturn_midi_68k_silent_batch_consumer_image() -> SaturnMidi68KSilentBatchConsumerImage:
    """Build the first silent full-batch resident MC68EC000 machine-code image."""

    assets = build_srk_saturn_midi_bridge_assets()
    preload = build_srk_saturn_midi_preload_image()
    if len(assets.program.records) != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchConsumerError(
            "canonical MIDI diagnostic record count changed unexpectedly"
        )
    if preload.mailbox_words[9] != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchConsumerError("canonical mailbox queue count changed")
    if preload.mailbox_words[6] != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchConsumerError("canonical mailbox write index changed")

    result = simulate_srk_saturn_midi_68k_command_engine(assets.program)
    if result.processed_records != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchConsumerError("silent model did not consume the full batch")
    if result.read_index != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchConsumerError("silent model read index changed unexpectedly")
    if result.last_error != 0:
        raise SaturnMidi68KSilentBatchConsumerError("silent model no longer finishes cleanly")

    summary_words = pack_srk_saturn_midi_68k_state_words(result)
    controller_words = _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(result))
    active_note_words = _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(result))

    asm = _Assembler68K()
    asm.label("poll")

    # Wait until the SH-2 producer publishes READY.
    asm.move_absw_to_dn(_MB_FLAGS, 0)
    asm.andi_w(SATURN_MIDI_MAILBOX_FLAG_READY, 0)
    asm.branch_word(0x6700, "poll")  # BEQ.W

    # Validate mailbox identity and the exact full-batch contract.
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
    asm.cmpi_w(SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS, 0)
    asm.branch_word(0x6600, "error_count")

    asm.move_absw_to_dn(_MB_WRITE_INDEX, 0)
    asm.cmpi_w(SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS, 0)
    asm.branch_word(0x6600, "error_count")

    # Publish diagnostic identity before validation.  READ_INDEX remains zero,
    # so this does not acknowledge partial progress.
    asm.move_imm_absw(
        SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC_OFFSET,
    )
    asm.move_imm_absw(
        SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION_OFFSET,
    )
    asm.move_imm_absw(
        0,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET,
    )
    asm.move_imm_absw(
        0,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET,
    )

    # Validate every queue word.  The current-record telemetry identifies the
    # failing record without ever moving the public mailbox READ_INDEX early.
    for record_index in range(SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS):
        asm.move_imm_absw(
            record_index,
            SATURN_MIDI_68K_TELEMETRY_ADDRESS
            + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET,
        )
        for word_index in range(4):
            queue_word_index = record_index * 4 + word_index
            asm.move_absw_to_dn(SATURN_MIDI_QUEUE_ADDRESS + queue_word_index * 2, 0)
            asm.cmpi_w(preload.queue_words[queue_word_index], 0)
            asm.branch_word(0x6600, "error_record")

    # Publish the complete reviewed state only after the full queue validates.
    _emit_word_block(asm, SATURN_MIDI_68K_STATE_ADDRESS, summary_words)
    _emit_word_block(asm, SATURN_MIDI_68K_CONTROLLER_ADDRESS, controller_words)
    _emit_word_block(asm, SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, active_note_words)

    final_time_us = result.final_time_us
    asm.move_imm_absw(
        result.processed_records,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET,
    )
    asm.move_imm_absw(
        result.processed_records,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS
        + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET,
    )
    asm.move_imm_absw(
        (final_time_us >> 16) & 0xFFFF,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_HI_OFFSET,
    )
    asm.move_imm_absw(
        final_time_us & 0xFFFF,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_LO_OFFSET,
    )
    asm.move_imm_absw(
        1,
        SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET,
    )

    # Acknowledge the complete batch only after all validation and state writes.
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS, _MB_READ_INDEX)
    asm.move_absw_to_dn(_MB_WRITE_SEQUENCE, 0)
    asm.move_dn_absw(0, _MB_READ_SEQUENCE)
    asm.move_imm_absw(0, _MB_LAST_ERROR)

    asm.label("success_hold")
    asm.branch_short_self()

    asm.label("error_magic")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_MAGIC, _MB_LAST_ERROR)
    asm.branch_word(0x6000, "error_hold")

    asm.label("error_version")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_VERSION, _MB_LAST_ERROR)
    asm.branch_word(0x6000, "error_hold")

    asm.label("error_contract")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_CONTRACT, _MB_LAST_ERROR)
    asm.branch_word(0x6000, "error_hold")

    asm.label("error_empty")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_EMPTY, _MB_LAST_ERROR)
    asm.branch_word(0x6000, "error_hold")

    asm.label("error_count")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_COUNT, _MB_LAST_ERROR)
    asm.branch_word(0x6000, "error_hold")

    asm.label("error_record")
    asm.move_imm_absw(SATURN_MIDI_68K_SILENT_BATCH_ERROR_RECORD, _MB_LAST_ERROR)

    asm.label("error_hold")
    asm.branch_short_self()

    image = SaturnMidi68KSilentBatchConsumerImage(
        words=asm.finish(),
        queue_word_count=len(preload.queue_words),
        expected_records=SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS,
    )
    if image.queue_word_count != SATURN_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS * 4:
        raise SaturnMidi68KSilentBatchConsumerError("canonical queue word count changed unexpectedly")
    if image.end_address > SATURN_MIDI_68K_SILENT_BATCH_MAX_END:
        raise SaturnMidi68KSilentBatchConsumerError(
            "silent full-batch program no longer fits the reviewed 0x4000-0x7FFF window"
        )
    return image


def render_srk_saturn_midi_68k_silent_batch_header() -> str:
    image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_H",
            "#define SRK_SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_H",
            "",
            "/* Silent exact-batch MC68EC000 image. No SCSP voice writes. */",
            f"#define SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS 0x{SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_SILENT_BATCH_STACK_ADDRESS 0x{SATURN_MIDI_68K_SILENT_BATCH_STACK_ADDRESS:08X}UL",
            f"#define SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT {len(image.words)}u",
            f"#define SRK_MIDI_68K_SILENT_BATCH_PROGRAM_BYTE_SIZE {image.byte_size}u",
            f"#define SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS {image.expected_records}u",
            f"#define SRK_MIDI_68K_SILENT_BATCH_QUEUE_WORDS {image.queue_word_count}u",
            "",
            "extern const unsigned short srk_saturn_midi_68k_silent_batch_program[SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT];",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_silent_batch_source() -> str:
    image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
    lines = [
        '#include "srk_saturn_midi_68k_silent_batch_program.h"',
        "",
        "const unsigned short srk_saturn_midi_68k_silent_batch_program[SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT] = {",
    ]
    for offset in range(0, len(image.words), 8):
        chunk = image.words[offset : offset + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(("};", ""))
    return "\n".join(lines)
