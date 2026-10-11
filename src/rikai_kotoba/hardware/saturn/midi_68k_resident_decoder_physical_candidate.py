"""Seven-record silent physical-proof preload for the general 68K decoder.

The proof deliberately uses a non-R19 batch size and exercises every SRKM v1
opcode exactly once.  This module performs no hardware I/O; it defines the
reviewed program and renders the C89 preload producer/verifier that a later
physical candidate may explicitly bind.
"""

from __future__ import annotations

from .midi_bridge import SATURN_MIDI_QUEUE_CAPACITY
from .midi_mailbox import pack_saturn_midi_queue_words
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS = 7
SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US = 7000


def build_srk_saturn_midi_68k_resident_decoder_proof_program() -> SaturnMidiProgram:
    """Return the fixed seven-record all-opcode physical proof program."""

    records = (
        SaturnMidiRecord(1000, SaturnMidiOpcode.NOTE_OFF, 0, 60, 32),
        SaturnMidiRecord(2000, SaturnMidiOpcode.NOTE_ON, 1, 64, 100),
        SaturnMidiRecord(3000, SaturnMidiOpcode.POLY_AFTERTOUCH, 2, 67, 55),
        SaturnMidiRecord(4000, SaturnMidiOpcode.CONTROL_CHANGE, 3, 7, 90),
        SaturnMidiRecord(5000, SaturnMidiOpcode.PROGRAM_CHANGE, 4, 12, 0),
        SaturnMidiRecord(6000, SaturnMidiOpcode.CHANNEL_PRESSURE, 5, 70, 0),
        SaturnMidiRecord(7000, SaturnMidiOpcode.PITCH_BEND, 6, 0, 64),
    )
    program = SaturnMidiProgram(
        records=records,
        duration_us=SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
    )
    if len(program.records) != SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS:
        raise RuntimeError("resident decoder physical proof record count changed")
    if len(program.records) > SATURN_MIDI_QUEUE_CAPACITY:
        raise RuntimeError("resident decoder physical proof no longer fits one queue fill")
    if tuple(record.opcode for record in program.records) != tuple(SaturnMidiOpcode):
        raise RuntimeError("resident decoder physical proof must exercise every SRKM opcode once")
    return program


def render_srk_saturn_midi_68k_resident_decoder_proof_preload_header() -> str:
    """Render declarations for the still-unbound seven-record preload."""

    program = build_srk_saturn_midi_68k_resident_decoder_proof_program()
    queue_words = pack_saturn_midi_queue_words(program)
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_PRELOAD_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_PRELOAD_H",
            "",
            "/* Silent proof input only; publishing is explicit in the candidate runtime. */",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS {len(program.records)}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROOF_QUEUE_WORDS {len(queue_words)}u",
            f"#define SRK_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US {program.duration_us}UL",
            "",
            "void srk_saturn_midi_68k_resident_decoder_proof_preload_publish(void);",
            "int srk_saturn_midi_68k_resident_decoder_proof_preload_verify(void);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_decoder_proof_preload_source() -> str:
    """Render the C89 Sound-RAM producer/verifier for the seven-record proof."""

    program = build_srk_saturn_midi_68k_resident_decoder_proof_program()
    queue_words = pack_saturn_midi_queue_words(program)
    lines = [
        '#include "srk_saturn_midi_68k_resident_decoder_proof_preload.h"',
        '#include "srk_saturn_midi_generated.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_MIDI_68K_RESIDENT_PROOF_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
        "",
        "static const unsigned short srk_saturn_midi_68k_resident_proof_queue_words[] = {",
    ]
    for offset in range(0, len(queue_words), 8):
        chunk = queue_words[offset : offset + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(
        (
            "};",
            "",
            "static void srk_saturn_midi_68k_resident_proof_write_word(",
            "    unsigned long byte_address,",
            "    unsigned short value",
            ")",
            "{",
            "    SRK_MIDI_68K_RESIDENT_PROOF_SOUND_RAM[byte_address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_68k_resident_proof_read_word(",
            "    unsigned long byte_address",
            ")",
            "{",
            "    return SRK_MIDI_68K_RESIDENT_PROOF_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "void srk_saturn_midi_68k_resident_decoder_proof_preload_publish(void)",
            "{",
            "    unsigned long index;",
            "",
            "    /* Withdraw READY before changing the queue/mailbox contract. */",
            "    srk_saturn_midi_68k_resident_proof_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),",
            "        0u",
            "    );",
            "",
            "    for(index=0UL; index<SRK_MIDI_68K_RESIDENT_DECODER_PROOF_QUEUE_WORDS; index++)",
            "        srk_saturn_midi_68k_resident_proof_write_word(",
            "            SRK_MIDI_QUEUE_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_resident_proof_queue_words[index]",
            "        );",
            "",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL), SRK_MIDI_MAILBOX_MAGIC0);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL), SRK_MIDI_MAILBOX_MAGIC1);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL), SRK_MIDI_MAILBOX_VERSION);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL), SRK_MIDI_PRELOAD_WRITE_SEQUENCE);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL), SRK_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL), SRK_MIDI_QUEUE_CAPACITY);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), SRK_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_RESERVED * 2UL), 0u);",
            "",
            "    /* READY is published last so the 68K cannot observe a partial proof batch. */",
            "    srk_saturn_midi_68k_resident_proof_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),",
            "        SRK_MIDI_MAILBOX_FLAG_READY",
            "    );",
            "}",
            "",
            "int srk_saturn_midi_68k_resident_decoder_proof_preload_verify(void)",
            "{",
            "    unsigned long index;",
            "",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC0)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC1)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL)) != SRK_MIDI_MAILBOX_VERSION)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL)) != SRK_MIDI_PRELOAD_WRITE_SEQUENCE)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL)) != SRK_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL)) != 0u)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL)) != SRK_MIDI_QUEUE_CAPACITY)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL)) != SRK_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS)",
            "        return 0;",
            "    if(srk_saturn_midi_68k_resident_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL)) != 0u)",
            "        return 0;",
            "",
            "    for(index=0UL; index<SRK_MIDI_68K_RESIDENT_DECODER_PROOF_QUEUE_WORDS; index++){",
            "        if(srk_saturn_midi_68k_resident_proof_read_word(",
            "            SRK_MIDI_QUEUE_ADDRESS + (index * 2UL)",
            "        ) != srk_saturn_midi_68k_resident_proof_queue_words[index])",
            "            return 0;",
            "    }",
            "",
            "    return (srk_saturn_midi_68k_resident_proof_read_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL)",
            "    ) & SRK_MIDI_MAILBOX_FLAG_READY) != 0u;",
            "}",
            "",
        )
    )
    return "\n".join(lines)
