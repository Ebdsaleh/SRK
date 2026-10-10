"""Saturn-facing deterministic MIDI bridge assets for the standalone diagnostic.

This module still performs no hardware I/O.  It defines SRK-owned Sound RAM
layout, a bounded SH-2/MC68EC000 mailbox contract, a tiny deterministic PCM tone
bank, and C89-friendly source rendering for the already-normalized SRKM event
program.  Hardware launch is intentionally deferred to a later tranche.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from rikai_kotoba.formats.midi import parse_midi_bytes
from rikai_kotoba.formats.midi_diagnostic import build_srk_midi_diagnostic_bytes
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiProgram,
    compile_saturn_midi_program,
)


SATURN_SOUND_RAM_BYTES = 512 * 1024

SATURN_MIDI_MAILBOX_ADDRESS = 0x00001000
SATURN_MIDI_MAILBOX_BYTES = 0x00000100
SATURN_MIDI_QUEUE_ADDRESS = 0x00001100
SATURN_MIDI_QUEUE_CAPACITY = 32
SATURN_MIDI_QUEUE_RECORD_BYTES = 8
SATURN_MIDI_QUEUE_BYTES = SATURN_MIDI_QUEUE_CAPACITY * SATURN_MIDI_QUEUE_RECORD_BYTES

SATURN_MIDI_TONE_BANK_ADDRESS = 0x00003000
SATURN_MIDI_TONE_COUNT = 3
SATURN_MIDI_TONE_SAMPLES = 64
SATURN_MIDI_TONE_SAMPLE_BYTES = 2
SATURN_MIDI_TONE_BANK_BYTES = (
    SATURN_MIDI_TONE_COUNT * SATURN_MIDI_TONE_SAMPLES * SATURN_MIDI_TONE_SAMPLE_BYTES
)

SATURN_MIDI_MAILBOX_MAGIC0 = 0x5352
SATURN_MIDI_MAILBOX_MAGIC1 = 0x4B4D
SATURN_MIDI_MAILBOX_VERSION = 1
SATURN_MIDI_MAILBOX_WORD_MAGIC0 = 0
SATURN_MIDI_MAILBOX_WORD_MAGIC1 = 1
SATURN_MIDI_MAILBOX_WORD_VERSION = 2
SATURN_MIDI_MAILBOX_WORD_FLAGS = 3
SATURN_MIDI_MAILBOX_WORD_WRITE_SEQUENCE = 4
SATURN_MIDI_MAILBOX_WORD_READ_SEQUENCE = 5
SATURN_MIDI_MAILBOX_WORD_WRITE_INDEX = 6
SATURN_MIDI_MAILBOX_WORD_READ_INDEX = 7
SATURN_MIDI_MAILBOX_WORD_QUEUE_CAPACITY = 8
SATURN_MIDI_MAILBOX_WORD_QUEUE_COUNT = 9
SATURN_MIDI_MAILBOX_WORD_LAST_ERROR = 10
SATURN_MIDI_MAILBOX_WORD_RESERVED = 11

# Existing standalone Audio/SCSP ownership that this bridge must not overlap.
_EXISTING_OWNED_RANGES = (
    (0x00000000, 0x00000402, "68K vectors/dummy loop"),
    (0x00002000, 0x000020CA, "Stage 1 deterministic tone"),
    (0x00002400, 0x00002602, "Stage 4 shaped PCM"),
    (0x00002800, 0x00002C02, "Stage 6 packaged PCM"),
)


class SaturnMidiBridgeError(RuntimeError):
    """Raised when deterministic MIDI bridge assets violate their contract."""


@dataclass(frozen=True)
class SaturnMidiBridgeAssets:
    program: SaturnMidiProgram
    tone_bank: tuple[tuple[int, ...], ...]
    header_text: str
    source_text: str

    @property
    def header_sha256(self) -> str:
        return sha256(self.header_text.encode("utf-8")).hexdigest()

    @property
    def source_sha256(self) -> str:
        return sha256(self.source_text.encode("utf-8")).hexdigest()


def _u16(value: int) -> int:
    return value & 0xFFFF


def build_srk_saturn_midi_tone_bank() -> tuple[tuple[int, ...], ...]:
    """Return three deterministic 64-sample signed-PCM16 waveforms as U16 words."""

    square = tuple(0x3000 if index < 32 else 0xD000 for index in range(64))

    triangle_values: list[int] = []
    for index in range(64):
        if index < 16:
            value = index * 0x0300
        elif index < 32:
            value = (32 - index) * 0x0300
        elif index < 48:
            value = -(index - 32) * 0x0300
        else:
            value = -(64 - index) * 0x0300
        triangle_values.append(_u16(value))
    triangle = tuple(triangle_values)

    saw = tuple(_u16(-0x3000 + index * 0x0180) for index in range(64))
    return (square, triangle, saw)


def _overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def validate_srk_saturn_midi_layout() -> None:
    """Prove the proposed bridge regions are bounded and do not overlap owned audio."""

    regions = (
        (
            SATURN_MIDI_MAILBOX_ADDRESS,
            SATURN_MIDI_MAILBOX_ADDRESS + SATURN_MIDI_MAILBOX_BYTES,
            "MIDI mailbox",
        ),
        (
            SATURN_MIDI_QUEUE_ADDRESS,
            SATURN_MIDI_QUEUE_ADDRESS + SATURN_MIDI_QUEUE_BYTES,
            "MIDI queue",
        ),
        (
            SATURN_MIDI_TONE_BANK_ADDRESS,
            SATURN_MIDI_TONE_BANK_ADDRESS + SATURN_MIDI_TONE_BANK_BYTES,
            "MIDI tone bank",
        ),
    )

    for start, end, label in regions:
        if start < 0 or end > SATURN_SOUND_RAM_BYTES or start >= end:
            raise SaturnMidiBridgeError(f"{label} lies outside Saturn Sound RAM")

    for index, (start, end, label) in enumerate(regions):
        for other_start, other_end, other_label in regions[index + 1 :]:
            if _overlap(start, end, other_start, other_end):
                raise SaturnMidiBridgeError(f"{label} overlaps {other_label}")
        for owned_start, owned_end, owned_label in _EXISTING_OWNED_RANGES:
            if _overlap(start, end, owned_start, owned_end):
                raise SaturnMidiBridgeError(f"{label} overlaps {owned_label}")

    if SATURN_MIDI_QUEUE_CAPACITY < 1:
        raise SaturnMidiBridgeError("MIDI queue capacity must be positive")


def _canonical_program() -> SaturnMidiProgram:
    midi = parse_midi_bytes(build_srk_midi_diagnostic_bytes())
    return compile_saturn_midi_program(midi)


def _render_header(program: SaturnMidiProgram) -> str:
    lines = [
        "#ifndef SRK_SATURN_MIDI_GENERATED_H",
        "#define SRK_SATURN_MIDI_GENERATED_H",
        "",
        "/* Generated by SRK. Hardware launch is not enabled by this file. */",
        "#define SRK_MIDI_MAILBOX_ADDRESS 0x00001000UL",
        "#define SRK_MIDI_MAILBOX_BYTES 0x00000100UL",
        "#define SRK_MIDI_QUEUE_ADDRESS 0x00001100UL",
        f"#define SRK_MIDI_QUEUE_CAPACITY {SATURN_MIDI_QUEUE_CAPACITY}u",
        f"#define SRK_MIDI_QUEUE_RECORD_BYTES {SATURN_MIDI_QUEUE_RECORD_BYTES}u",
        "#define SRK_MIDI_TONE_BANK_ADDRESS 0x00003000UL",
        f"#define SRK_MIDI_TONE_COUNT {SATURN_MIDI_TONE_COUNT}u",
        f"#define SRK_MIDI_TONE_SAMPLES {SATURN_MIDI_TONE_SAMPLES}u",
        f"#define SRK_MIDI_EVENT_COUNT {len(program.records)}UL",
        f"#define SRK_MIDI_DURATION_US {program.duration_us}UL",
        "",
        "#define SRK_MIDI_MAILBOX_MAGIC0 0x5352u",
        "#define SRK_MIDI_MAILBOX_MAGIC1 0x4B4Du",
        "#define SRK_MIDI_MAILBOX_VERSION 1u",
        "#define SRK_MIDI_MB_MAGIC0 0u",
        "#define SRK_MIDI_MB_MAGIC1 1u",
        "#define SRK_MIDI_MB_VERSION 2u",
        "#define SRK_MIDI_MB_FLAGS 3u",
        "#define SRK_MIDI_MB_WRITE_SEQUENCE 4u",
        "#define SRK_MIDI_MB_READ_SEQUENCE 5u",
        "#define SRK_MIDI_MB_WRITE_INDEX 6u",
        "#define SRK_MIDI_MB_READ_INDEX 7u",
        "#define SRK_MIDI_MB_QUEUE_CAPACITY 8u",
        "#define SRK_MIDI_MB_QUEUE_COUNT 9u",
        "#define SRK_MIDI_MB_LAST_ERROR 10u",
        "#define SRK_MIDI_MB_RESERVED 11u",
        "",
        "typedef struct SRK_SATURN_MIDI_EVENT {",
        "    unsigned long time_us;",
        "    unsigned char opcode;",
        "    unsigned char channel;",
        "    unsigned char data0;",
        "    unsigned char data1;",
        "} SRK_SATURN_MIDI_EVENT;",
        "",
        "extern const SRK_SATURN_MIDI_EVENT srk_saturn_midi_events[SRK_MIDI_EVENT_COUNT];",
        "extern const unsigned short srk_saturn_midi_tone_bank[SRK_MIDI_TONE_COUNT][SRK_MIDI_TONE_SAMPLES];",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def _render_source(
    program: SaturnMidiProgram,
    tone_bank: tuple[tuple[int, ...], ...],
) -> str:
    lines = [
        '#include "srk_saturn_midi_generated.h"',
        "",
        "const SRK_SATURN_MIDI_EVENT srk_saturn_midi_events[SRK_MIDI_EVENT_COUNT] = {",
    ]
    for record in program.records:
        lines.append(
            "    {%dUL, %du, %du, %du, %du},"
            % (
                record.time_us,
                int(record.opcode),
                record.channel,
                record.data0,
                record.data1,
            )
        )
    lines.extend(("};", "", "const unsigned short srk_saturn_midi_tone_bank[SRK_MIDI_TONE_COUNT][SRK_MIDI_TONE_SAMPLES] = {"))
    for waveform in tone_bank:
        lines.append("    {")
        for offset in range(0, len(waveform), 8):
            chunk = waveform[offset : offset + 8]
            lines.append("        " + ", ".join(f"0x{value:04X}u" for value in chunk) + ",")
        lines.append("    },")
    lines.extend(("};", ""))
    return "\n".join(lines)


def build_srk_saturn_midi_bridge_assets() -> SaturnMidiBridgeAssets:
    """Build deterministic C bridge inputs without touching Saturn hardware."""

    validate_srk_saturn_midi_layout()
    program = _canonical_program()
    if len(program.records) > SATURN_MIDI_QUEUE_CAPACITY:
        raise SaturnMidiBridgeError(
            "canonical MIDI diagnostic does not fit one bounded queue fill"
        )
    tone_bank = build_srk_saturn_midi_tone_bank()
    if len(tone_bank) != SATURN_MIDI_TONE_COUNT:
        raise SaturnMidiBridgeError("unexpected MIDI tone count")
    if any(len(waveform) != SATURN_MIDI_TONE_SAMPLES for waveform in tone_bank):
        raise SaturnMidiBridgeError("unexpected MIDI tone sample count")
    return SaturnMidiBridgeAssets(
        program=program,
        tone_bank=tone_bank,
        header_text=_render_header(program),
        source_text=_render_source(program, tone_bank),
    )
