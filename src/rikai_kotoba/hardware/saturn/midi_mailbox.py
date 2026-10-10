"""Deterministic SH-2 -> MC68EC000 MIDI preload contract.

This module defines the exact Sound-RAM words SRK will publish before the future
MC68EC000 consumer is allowed to run.  It still performs no hardware I/O.

The producer contract deliberately uses 16-bit Sound-RAM words so it matches the
already accepted standalone Audio/SCSP access policy and avoids compiler struct
layout/endian assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .midi_bridge import (
    SATURN_MIDI_MAILBOX_MAGIC0,
    SATURN_MIDI_MAILBOX_MAGIC1,
    SATURN_MIDI_MAILBOX_VERSION,
    SATURN_MIDI_QUEUE_CAPACITY,
    SATURN_MIDI_TONE_COUNT,
    SATURN_MIDI_TONE_SAMPLES,
    build_srk_saturn_midi_bridge_assets,
)
from .midi_program import SaturnMidiProgram


SATURN_MIDI_MAILBOX_FLAG_READY = 0x0001
SATURN_MIDI_MAILBOX_WORD_COUNT = 12
SATURN_MIDI_PRELOAD_WRITE_SEQUENCE = 1


class SaturnMidiMailboxError(RuntimeError):
    """Raised when a normalized MIDI program cannot satisfy the preload contract."""


@dataclass(frozen=True)
class SaturnMidiPreloadImage:
    mailbox_words: tuple[int, ...]
    queue_words: tuple[int, ...]
    tone_words: tuple[int, ...]

    @property
    def all_words(self) -> tuple[int, ...]:
        return self.mailbox_words + self.queue_words + self.tone_words

    @property
    def byte_size(self) -> int:
        return len(self.all_words) * 2

    @property
    def sha256(self) -> str:
        payload = b"".join(word.to_bytes(2, "big") for word in self.all_words)
        return sha256(payload).hexdigest()


def _word(value: int, label: str) -> int:
    if value < 0 or value > 0xFFFF:
        raise SaturnMidiMailboxError(f"{label} is outside a 16-bit Sound-RAM word: {value}")
    return value


def pack_saturn_midi_queue_words(program: SaturnMidiProgram) -> tuple[int, ...]:
    """Serialize SRKM records into four big-endian Sound-RAM words each."""

    if not program.records:
        raise SaturnMidiMailboxError("MIDI preload requires at least one playback record")
    if len(program.records) > SATURN_MIDI_QUEUE_CAPACITY:
        raise SaturnMidiMailboxError(
            f"MIDI program has {len(program.records)} records but queue capacity is "
            f"{SATURN_MIDI_QUEUE_CAPACITY}"
        )

    words: list[int] = []
    previous_time = -1
    for record in program.records:
        if record.time_us < previous_time:
            raise SaturnMidiMailboxError("MIDI preload records are not chronological")
        if record.time_us < 0 or record.time_us > 0xFFFFFFFF:
            raise SaturnMidiMailboxError("MIDI preload timestamp exceeds 32-bit range")
        previous_time = record.time_us

        words.extend(
            (
                (record.time_us >> 16) & 0xFFFF,
                record.time_us & 0xFFFF,
                ((int(record.opcode) & 0xFF) << 8) | (record.channel & 0xFF),
                ((record.data0 & 0xFF) << 8) | (record.data1 & 0xFF),
            )
        )
    return tuple(words)


def build_saturn_midi_mailbox_words(program: SaturnMidiProgram) -> tuple[int, ...]:
    """Return the 12 published mailbox words for one preloaded queue batch."""

    count = len(program.records)
    if count < 1 or count > SATURN_MIDI_QUEUE_CAPACITY:
        raise SaturnMidiMailboxError("MIDI preload event count does not fit the bounded queue")

    words = (
        SATURN_MIDI_MAILBOX_MAGIC0,
        SATURN_MIDI_MAILBOX_MAGIC1,
        SATURN_MIDI_MAILBOX_VERSION,
        SATURN_MIDI_MAILBOX_FLAG_READY,
        SATURN_MIDI_PRELOAD_WRITE_SEQUENCE,
        0,
        count,
        0,
        SATURN_MIDI_QUEUE_CAPACITY,
        count,
        0,
        0,
    )
    if len(words) != SATURN_MIDI_MAILBOX_WORD_COUNT:
        raise SaturnMidiMailboxError("MIDI mailbox word count changed unexpectedly")
    return tuple(_word(value, "mailbox value") for value in words)


def build_srk_saturn_midi_preload_image() -> SaturnMidiPreloadImage:
    """Build the canonical queue/mailbox/tone image without writing Sound RAM."""

    assets = build_srk_saturn_midi_bridge_assets()
    tone_words = tuple(value for waveform in assets.tone_bank for value in waveform)
    if len(tone_words) != SATURN_MIDI_TONE_COUNT * SATURN_MIDI_TONE_SAMPLES:
        raise SaturnMidiMailboxError("canonical MIDI tone-bank size changed unexpectedly")

    image = SaturnMidiPreloadImage(
        mailbox_words=build_saturn_midi_mailbox_words(assets.program),
        queue_words=pack_saturn_midi_queue_words(assets.program),
        tone_words=tuple(_word(value, "tone sample") for value in tone_words),
    )
    expected_queue_words = len(assets.program.records) * 4
    if len(image.queue_words) != expected_queue_words:
        raise SaturnMidiMailboxError("canonical MIDI queue size changed unexpectedly")
    return image


def render_srk_saturn_midi_mailbox_header() -> str:
    """Render the C89 header for the still-uninvoked SH-2 preload producer."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_MAILBOX_H",
            "#define SRK_SATURN_MIDI_MAILBOX_H",
            "",
            "/* SH-2 producer only. This header does not launch the MC68EC000. */",
            f"#define SRK_MIDI_MAILBOX_FLAG_READY 0x{SATURN_MIDI_MAILBOX_FLAG_READY:04X}u",
            f"#define SRK_MIDI_MAILBOX_WORD_COUNT {SATURN_MIDI_MAILBOX_WORD_COUNT}u",
            f"#define SRK_MIDI_PRELOAD_WRITE_SEQUENCE {SATURN_MIDI_PRELOAD_WRITE_SEQUENCE}u",
            "",
            "void srk_saturn_midi_preload_publish(void);",
            "void srk_saturn_midi_preload_unpublish(void);",
            "int srk_saturn_midi_preload_is_ready(void);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_mailbox_source() -> str:
    """Render a C89 SH-2 producer; no function is called by the diagnostic yet."""

    return "\n".join(
        (
            '#include "srk_saturn_midi_mailbox.h"',
            '#include "srk_saturn_midi_generated.h"',
            "",
            "#define SRK_MIDI_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
            "",
            "static void srk_saturn_midi_write_word(unsigned long byte_address, unsigned short value)",
            "{",
            "    SRK_MIDI_SOUND_RAM[byte_address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_read_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "void srk_saturn_midi_preload_publish(void)",
            "{",
            "    unsigned long index;",
            "    unsigned long base;",
            "    const SRK_SATURN_MIDI_EVENT *event;",
            "",
            "    /* Withdraw READY before changing queue/tone state. */",
            "    srk_saturn_midi_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),",
            "        0u",
            "    );",
            "",
            "    base = SRK_MIDI_TONE_BANK_ADDRESS;",
            "    for(index=0UL; index<(unsigned long)(SRK_MIDI_TONE_COUNT * SRK_MIDI_TONE_SAMPLES); index++)",
            "        srk_saturn_midi_write_word(",
            "            base + (index * 2UL),",
            "            srk_saturn_midi_tone_bank[index / SRK_MIDI_TONE_SAMPLES][index % SRK_MIDI_TONE_SAMPLES]",
            "        );",
            "",
            "    base = SRK_MIDI_QUEUE_ADDRESS;",
            "    for(index=0UL; index<SRK_MIDI_EVENT_COUNT; index++){",
            "        event = &srk_saturn_midi_events[index];",
            "        srk_saturn_midi_write_word(base + (index * 8UL) + 0UL, (unsigned short)(event->time_us >> 16));",
            "        srk_saturn_midi_write_word(base + (index * 8UL) + 2UL, (unsigned short)(event->time_us & 0xFFFFUL));",
            "        srk_saturn_midi_write_word(base + (index * 8UL) + 4UL, (unsigned short)(((unsigned short)event->opcode << 8) | event->channel));",
            "        srk_saturn_midi_write_word(base + (index * 8UL) + 6UL, (unsigned short)(((unsigned short)event->data0 << 8) | event->data1));",
            "    }",
            "",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL), SRK_MIDI_MAILBOX_MAGIC0);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL), SRK_MIDI_MAILBOX_MAGIC1);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL), SRK_MIDI_MAILBOX_VERSION);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL), SRK_MIDI_PRELOAD_WRITE_SEQUENCE);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL), 0u);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL), (unsigned short)SRK_MIDI_EVENT_COUNT);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL), 0u);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL), SRK_MIDI_QUEUE_CAPACITY);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), (unsigned short)SRK_MIDI_EVENT_COUNT);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL), 0u);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_RESERVED * 2UL), 0u);",
            "",
            "    /* Publish READY last so the future consumer cannot observe a partial batch. */",
            "    srk_saturn_midi_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),",
            "        SRK_MIDI_MAILBOX_FLAG_READY",
            "    );",
            "}",
            "",
            "void srk_saturn_midi_preload_unpublish(void)",
            "{",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL), 0u);",
            "    srk_saturn_midi_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), 0u);",
            "}",
            "",
            "int srk_saturn_midi_preload_is_ready(void)",
            "{",
            "    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC0)",
            "        return 0;",
            "    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC1)",
            "        return 0;",
            "    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL)) != SRK_MIDI_MAILBOX_VERSION)",
            "        return 0;",
            "    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL)) != SRK_MIDI_QUEUE_CAPACITY)",
            "        return 0;",
            "    if(srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL)) != (unsigned short)SRK_MIDI_EVENT_COUNT)",
            "        return 0;",
            "    return (srk_saturn_midi_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL)) & SRK_MIDI_MAILBOX_FLAG_READY) != 0u;",
            "}",
            "",
        )
    )
