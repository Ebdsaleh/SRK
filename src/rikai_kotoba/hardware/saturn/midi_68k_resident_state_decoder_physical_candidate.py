"""Phase-B physical proof program and full Sound-RAM state verifier.

The proof remains silent.  It supplies a richer 20-record SRKM v1 batch and
derives the complete expected post-execution MIDI state from the existing
host-side command-engine model.  The generated SH-2 verifier compares every
channel-summary word, every controller word and every active-note bitmap word
after the MC68EC000 acknowledges the batch.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
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
    SATURN_MIDI_68K_STATE_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
    simulate_srk_saturn_midi_68k_command_engine,
)
from .midi_bridge import SATURN_MIDI_QUEUE_CAPACITY
from .midi_mailbox import pack_saturn_midi_queue_words
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS = 20
SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US = 20000
SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRIMARY_CHANNEL = 3
SATURN_MIDI_68K_RESIDENT_STATE_PROOF_SECONDARY_CHANNEL = 9
SATURN_MIDI_68K_RESIDENT_STATE_PROOF_ARBITRARY_CONTROLLER = 74

SATURN_MIDI_68K_STATE_VERIFY_NOT_RUN = 0
SATURN_MIDI_68K_STATE_VERIFY_PASS = 1
SATURN_MIDI_68K_STATE_VERIFY_SUMMARY_MISMATCH = 2
SATURN_MIDI_68K_STATE_VERIFY_CONTROLLER_MISMATCH = 3
SATURN_MIDI_68K_STATE_VERIFY_ACTIVE_NOTE_MISMATCH = 4


@dataclass(frozen=True)
class SaturnMidi68KResidentStateProofSnapshot:
    ch3_program: int
    ch3_bank_msb: int
    ch3_bank_lsb: int
    ch3_volume: int
    ch3_pan: int
    ch3_expression: int
    ch3_sustain: int
    ch3_channel_pressure: int
    ch3_pitch_bend: int
    ch3_last_note: int
    ch3_last_velocity: int
    ch3_last_poly_note: int
    ch3_last_poly_pressure: int
    ch3_active_note_count: int
    ch3_event_count: int
    ch3_last_opcode: int
    ch3_cc74: int
    ch3_active_bitmap_byte: int
    ch9_program: int
    ch9_volume: int
    ch9_pitch_bend: int
    ch9_last_note: int
    ch9_last_velocity: int
    ch9_active_note_count: int
    ch9_active_bitmap_byte: int


def build_srk_saturn_midi_68k_resident_state_proof_program() -> SaturnMidiProgram:
    """Return the reviewed richer Phase-B physical proof program."""

    ch = SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRIMARY_CHANNEL
    ch2 = SATURN_MIDI_68K_RESIDENT_STATE_PROOF_SECONDARY_CHANNEL
    records = (
        SaturnMidiRecord(1000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 0, 5),
        SaturnMidiRecord(2000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 32, 9),
        SaturnMidiRecord(3000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 7, 91),
        SaturnMidiRecord(4000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 10, 73),
        SaturnMidiRecord(5000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 11, 101),
        SaturnMidiRecord(6000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 64, 127),
        SaturnMidiRecord(7000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 74, 66),
        SaturnMidiRecord(8000, SaturnMidiOpcode.PROGRAM_CHANGE, ch, 12, 0),
        SaturnMidiRecord(9000, SaturnMidiOpcode.CHANNEL_PRESSURE, ch, 70, 0),
        SaturnMidiRecord(10000, SaturnMidiOpcode.PITCH_BEND, ch, 52, 78),
        SaturnMidiRecord(11000, SaturnMidiOpcode.NOTE_ON, ch, 64, 100),
        SaturnMidiRecord(12000, SaturnMidiOpcode.NOTE_ON, ch, 69, 88),
        SaturnMidiRecord(13000, SaturnMidiOpcode.POLY_AFTERTOUCH, ch, 64, 55),
        SaturnMidiRecord(14000, SaturnMidiOpcode.NOTE_OFF, ch, 64, 32),
        SaturnMidiRecord(15000, SaturnMidiOpcode.NOTE_ON, ch, 69, 0),
        SaturnMidiRecord(16000, SaturnMidiOpcode.NOTE_ON, ch, 64, 77),
        SaturnMidiRecord(17000, SaturnMidiOpcode.PROGRAM_CHANGE, ch2, 33, 0),
        SaturnMidiRecord(18000, SaturnMidiOpcode.CONTROL_CHANGE, ch2, 7, 84),
        SaturnMidiRecord(19000, SaturnMidiOpcode.NOTE_ON, ch2, 48, 96),
        SaturnMidiRecord(20000, SaturnMidiOpcode.PITCH_BEND, ch2, 0, 32),
    )
    program = SaturnMidiProgram(
        records=records,
        duration_us=SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US,
    )
    if len(program.records) != SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS:
        raise RuntimeError("resident state proof record count changed")
    if len(program.records) > SATURN_MIDI_QUEUE_CAPACITY:
        raise RuntimeError("resident state proof no longer fits one queue fill")
    if set(record.opcode for record in program.records) != set(SaturnMidiOpcode):
        raise RuntimeError("resident state proof must exercise all SRKM v1 opcodes")
    return program


def build_srk_saturn_midi_68k_resident_state_proof_snapshot() -> SaturnMidi68KResidentStateProofSnapshot:
    program = build_srk_saturn_midi_68k_resident_state_proof_program()
    result = simulate_srk_saturn_midi_68k_command_engine(program)
    primary = result.channels[SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRIMARY_CHANNEL]
    secondary = result.channels[SATURN_MIDI_68K_RESIDENT_STATE_PROOF_SECONDARY_CHANNEL]
    active = pack_srk_saturn_midi_68k_active_note_bitmap(result)
    primary_bitmap = active[
        SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRIMARY_CHANNEL * 16 + (64 >> 3)
    ]
    secondary_bitmap = active[
        SATURN_MIDI_68K_RESIDENT_STATE_PROOF_SECONDARY_CHANNEL * 16 + (48 >> 3)
    ]
    return SaturnMidi68KResidentStateProofSnapshot(
        ch3_program=primary.program,
        ch3_bank_msb=primary.bank_msb,
        ch3_bank_lsb=primary.bank_lsb,
        ch3_volume=primary.volume,
        ch3_pan=primary.pan,
        ch3_expression=primary.expression,
        ch3_sustain=primary.sustain,
        ch3_channel_pressure=primary.channel_pressure,
        ch3_pitch_bend=primary.pitch_bend,
        ch3_last_note=primary.last_note,
        ch3_last_velocity=primary.last_velocity,
        ch3_last_poly_note=primary.last_poly_note,
        ch3_last_poly_pressure=primary.last_poly_pressure,
        ch3_active_note_count=primary.active_note_count,
        ch3_event_count=primary.event_count,
        ch3_last_opcode=primary.last_opcode,
        ch3_cc74=primary.controllers[SATURN_MIDI_68K_RESIDENT_STATE_PROOF_ARBITRARY_CONTROLLER],
        ch3_active_bitmap_byte=primary_bitmap,
        ch9_program=secondary.program,
        ch9_volume=secondary.volume,
        ch9_pitch_bend=secondary.pitch_bend,
        ch9_last_note=secondary.last_note,
        ch9_last_velocity=secondary.last_velocity,
        ch9_active_note_count=secondary.active_note_count,
        ch9_active_bitmap_byte=secondary_bitmap,
    )


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise RuntimeError("state proof payload must be word aligned")
    return tuple(
        (payload[index] << 8) | payload[index + 1]
        for index in range(0, len(payload), 2)
    )


def build_srk_saturn_midi_68k_resident_state_expected_words() -> tuple[
    tuple[int, ...], tuple[int, ...], tuple[int, ...]
]:
    result = simulate_srk_saturn_midi_68k_command_engine(
        build_srk_saturn_midi_68k_resident_state_proof_program()
    )
    return (
        pack_srk_saturn_midi_68k_state_words(result),
        _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(result)),
        _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(result)),
    )


def render_srk_saturn_midi_68k_resident_state_proof_preload_header() -> str:
    program = build_srk_saturn_midi_68k_resident_state_proof_program()
    queue_words = pack_saturn_midi_queue_words(program)
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRELOAD_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_PROOF_PRELOAD_H",
            "",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS {len(program.records)}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_PROOF_QUEUE_WORDS {len(queue_words)}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US {program.duration_us}UL",
            "",
            "void srk_saturn_midi_68k_resident_state_proof_preload_publish(void);",
            "int srk_saturn_midi_68k_resident_state_proof_preload_verify(void);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_resident_state_proof_preload_source() -> str:
    program = build_srk_saturn_midi_68k_resident_state_proof_program()
    queue_words = pack_saturn_midi_queue_words(program)
    lines = [
        '#include "srk_saturn_midi_68k_resident_state_proof_preload.h"',
        '#include "srk_saturn_midi_generated.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_MIDI_68K_RESIDENT_STATE_PROOF_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
        "",
        "static const unsigned short srk_saturn_midi_68k_resident_state_proof_queue_words[] = {",
    ]
    for offset in range(0, len(queue_words), 8):
        chunk = queue_words[offset : offset + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(
        (
            "};",
            "",
            "static void srk_saturn_midi_68k_resident_state_proof_write_word(",
            "    unsigned long byte_address, unsigned short value)",
            "{",
            "    SRK_MIDI_68K_RESIDENT_STATE_PROOF_SOUND_RAM[byte_address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_saturn_midi_68k_resident_state_proof_read_word(",
            "    unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_68K_RESIDENT_STATE_PROOF_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "void srk_saturn_midi_68k_resident_state_proof_preload_publish(void)",
            "{",
            "    unsigned long index;",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL), 0u);",
            "    for(index=0UL; index<SRK_MIDI_68K_RESIDENT_STATE_PROOF_QUEUE_WORDS; index++)",
            "        srk_saturn_midi_68k_resident_state_proof_write_word(",
            "            SRK_MIDI_QUEUE_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_resident_state_proof_queue_words[index]);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL), SRK_MIDI_MAILBOX_MAGIC0);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL), SRK_MIDI_MAILBOX_MAGIC1);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL), SRK_MIDI_MAILBOX_VERSION);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL), SRK_MIDI_PRELOAD_WRITE_SEQUENCE);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL), SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL), SRK_MIDI_QUEUE_CAPACITY);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL), SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_RESERVED * 2UL), 0u);",
            "    srk_saturn_midi_68k_resident_state_proof_write_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL),",
            "        SRK_MIDI_MAILBOX_FLAG_READY);",
            "}",
            "",
            "int srk_saturn_midi_68k_resident_state_proof_preload_verify(void)",
            "{",
            "    unsigned long index;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC0 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC0) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_MAGIC1 * 2UL)) != SRK_MIDI_MAILBOX_MAGIC1) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_VERSION * 2UL)) != SRK_MIDI_MAILBOX_VERSION) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_SEQUENCE * 2UL)) != SRK_MIDI_PRELOAD_WRITE_SEQUENCE) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_SEQUENCE * 2UL)) != 0u) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_WRITE_INDEX * 2UL)) != SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_READ_INDEX * 2UL)) != 0u) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_CAPACITY * 2UL)) != SRK_MIDI_QUEUE_CAPACITY) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_QUEUE_COUNT * 2UL)) != SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS) return 0;",
            "    if(srk_saturn_midi_68k_resident_state_proof_read_word(SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_LAST_ERROR * 2UL)) != 0u) return 0;",
            "    for(index=0UL; index<SRK_MIDI_68K_RESIDENT_STATE_PROOF_QUEUE_WORDS; index++)",
            "        if(srk_saturn_midi_68k_resident_state_proof_read_word(",
            "            SRK_MIDI_QUEUE_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_resident_state_proof_queue_words[index]) return 0;",
            "    return (srk_saturn_midi_68k_resident_state_proof_read_word(",
            "        SRK_MIDI_MAILBOX_ADDRESS + (SRK_MIDI_MB_FLAGS * 2UL)) &",
            "        SRK_MIDI_MAILBOX_FLAG_READY) != 0u;",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def render_srk_saturn_midi_68k_resident_state_verifier_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFIER_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFIER_H",
            "",
            f"#define SRK_MIDI_68K_STATE_VERIFY_NOT_RUN {SATURN_MIDI_68K_STATE_VERIFY_NOT_RUN}u",
            f"#define SRK_MIDI_68K_STATE_VERIFY_PASS {SATURN_MIDI_68K_STATE_VERIFY_PASS}u",
            f"#define SRK_MIDI_68K_STATE_VERIFY_SUMMARY_MISMATCH {SATURN_MIDI_68K_STATE_VERIFY_SUMMARY_MISMATCH}u",
            f"#define SRK_MIDI_68K_STATE_VERIFY_CONTROLLER_MISMATCH {SATURN_MIDI_68K_STATE_VERIFY_CONTROLLER_MISMATCH}u",
            f"#define SRK_MIDI_68K_STATE_VERIFY_ACTIVE_NOTE_MISMATCH {SATURN_MIDI_68K_STATE_VERIFY_ACTIVE_NOTE_MISMATCH}u",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT {",
            "    unsigned short status;",
            "    unsigned short mismatch_index;",
            "    unsigned short expected_value;",
            "    unsigned short actual_value;",
            "    unsigned short ch3_program;",
            "    unsigned short ch3_bank_msb;",
            "    unsigned short ch3_bank_lsb;",
            "    unsigned short ch3_volume;",
            "    unsigned short ch3_pan;",
            "    unsigned short ch3_expression;",
            "    unsigned short ch3_sustain;",
            "    unsigned short ch3_channel_pressure;",
            "    unsigned short ch3_pitch_bend;",
            "    unsigned short ch3_last_note;",
            "    unsigned short ch3_last_velocity;",
            "    unsigned short ch3_last_poly_note;",
            "    unsigned short ch3_last_poly_pressure;",
            "    unsigned short ch3_active_note_count;",
            "    unsigned short ch3_event_count;",
            "    unsigned short ch3_last_opcode;",
            "    unsigned short ch3_cc74;",
            "    unsigned short ch3_active_bitmap_byte;",
            "    unsigned short ch9_program;",
            "    unsigned short ch9_volume;",
            "    unsigned short ch9_pitch_bend;",
            "    unsigned short ch9_last_note;",
            "    unsigned short ch9_last_velocity;",
            "    unsigned short ch9_active_note_count;",
            "    unsigned short ch9_active_bitmap_byte;",
            "} SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT;",
            "",
            "void srk_saturn_midi_68k_resident_state_verify_reset(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT *result);",
            "int srk_saturn_midi_68k_resident_state_verify(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT *result);",
            "",
            "#endif",
            "",
        )
    )


def _render_word_array(name: str, words: tuple[int, ...]) -> list[str]:
    lines = [f"static const unsigned short {name}[] = {{"]
    for offset in range(0, len(words), 8):
        chunk = words[offset : offset + 8]
        lines.append("    " + ", ".join(f"0x{word:04X}u" for word in chunk) + ",")
    lines.extend(("};", ""))
    return lines


def render_srk_saturn_midi_68k_resident_state_verifier_source() -> str:
    summaries, controllers, active = build_srk_saturn_midi_68k_resident_state_expected_words()
    lines = [
        '#include "srk_saturn_midi_68k_resident_state_verifier.h"',
        "",
        "#define SRK_MIDI_68K_STATE_VERIFY_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
        f"#define SRK_MIDI_68K_STATE_VERIFY_SUMMARY_ADDRESS 0x{SATURN_MIDI_68K_STATE_ADDRESS:08X}UL",
        f"#define SRK_MIDI_68K_STATE_VERIFY_CONTROLLER_ADDRESS 0x{SATURN_MIDI_68K_CONTROLLER_ADDRESS:08X}UL",
        f"#define SRK_MIDI_68K_STATE_VERIFY_ACTIVE_ADDRESS 0x{SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:08X}UL",
        f"#define SRK_MIDI_68K_STATE_VERIFY_CHANNEL_BYTES {SATURN_MIDI_68K_CHANNEL_STATE_BYTES}UL",
        "",
    ]
    lines.extend(_render_word_array("srk_midi_68k_expected_summary_words", summaries))
    lines.extend(_render_word_array("srk_midi_68k_expected_controller_words", controllers))
    lines.extend(_render_word_array("srk_midi_68k_expected_active_words", active))
    lines.extend(
        (
            "static unsigned short srk_midi_68k_state_read_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_68K_STATE_VERIFY_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "static unsigned short srk_midi_68k_state_read_channel(",
            "    unsigned int channel, unsigned int word_index)",
            "{",
            "    return srk_midi_68k_state_read_word(",
            "        SRK_MIDI_68K_STATE_VERIFY_SUMMARY_ADDRESS +",
            "        ((unsigned long)channel * SRK_MIDI_68K_STATE_VERIFY_CHANNEL_BYTES) +",
            "        ((unsigned long)word_index * 2UL));",
            "}",
            "",
            "static void srk_midi_68k_state_fill_snapshot(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT *result)",
            "{",
            "    unsigned short value;",
            "    if(!result) return;",
            f"    result->ch3_program = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_PROGRAM}u);",
            f"    result->ch3_bank_msb = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_BANK_MSB}u);",
            f"    result->ch3_bank_lsb = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_BANK_LSB}u);",
            f"    result->ch3_volume = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_VOLUME}u);",
            f"    result->ch3_pan = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_PAN}u);",
            f"    result->ch3_expression = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_EXPRESSION}u);",
            f"    result->ch3_sustain = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_SUSTAIN}u);",
            f"    result->ch3_channel_pressure = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_CHANNEL_PRESSURE}u);",
            f"    result->ch3_pitch_bend = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_PITCH_BEND}u);",
            f"    result->ch3_last_note = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_LAST_NOTE}u);",
            f"    result->ch3_last_velocity = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_LAST_VELOCITY}u);",
            f"    result->ch3_last_poly_note = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_LAST_POLY_NOTE}u);",
            f"    result->ch3_last_poly_pressure = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE}u);",
            f"    result->ch3_active_note_count = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT}u);",
            f"    result->ch3_event_count = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_EVENT_COUNT}u);",
            f"    result->ch3_last_opcode = srk_midi_68k_state_read_channel(3u, {SATURN_MIDI_68K_CH_LAST_OPCODE}u);",
            "    value = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_CONTROLLER_ADDRESS + (3UL * 128UL) + 74UL);",
            "    result->ch3_cc74 = (unsigned short)((value >> 8) & 0x00FFu);",
            "    value = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_ACTIVE_ADDRESS + (3UL * 16UL) + 8UL);",
            "    result->ch3_active_bitmap_byte = (unsigned short)((value >> 8) & 0x00FFu);",
            f"    result->ch9_program = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_PROGRAM}u);",
            f"    result->ch9_volume = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_VOLUME}u);",
            f"    result->ch9_pitch_bend = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_PITCH_BEND}u);",
            f"    result->ch9_last_note = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_LAST_NOTE}u);",
            f"    result->ch9_last_velocity = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_LAST_VELOCITY}u);",
            f"    result->ch9_active_note_count = srk_midi_68k_state_read_channel(9u, {SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT}u);",
            "    value = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_ACTIVE_ADDRESS + (9UL * 16UL) + 6UL);",
            "    result->ch9_active_bitmap_byte = (unsigned short)((value >> 8) & 0x00FFu);",
            "}",
            "",
            "void srk_saturn_midi_68k_resident_state_verify_reset(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT *result)",
            "{",
            "    if(!result) return;",
            "    result->status = SRK_MIDI_68K_STATE_VERIFY_NOT_RUN;",
            "    result->mismatch_index = 0u;",
            "    result->expected_value = 0u;",
            "    result->actual_value = 0u;",
            "    result->ch3_program = 0u;",
            "    result->ch3_bank_msb = 0u;",
            "    result->ch3_bank_lsb = 0u;",
            "    result->ch3_volume = 0u;",
            "    result->ch3_pan = 0u;",
            "    result->ch3_expression = 0u;",
            "    result->ch3_sustain = 0u;",
            "    result->ch3_channel_pressure = 0u;",
            "    result->ch3_pitch_bend = 0u;",
            "    result->ch3_last_note = 0u;",
            "    result->ch3_last_velocity = 0u;",
            "    result->ch3_last_poly_note = 0u;",
            "    result->ch3_last_poly_pressure = 0u;",
            "    result->ch3_active_note_count = 0u;",
            "    result->ch3_event_count = 0u;",
            "    result->ch3_last_opcode = 0u;",
            "    result->ch3_cc74 = 0u;",
            "    result->ch3_active_bitmap_byte = 0u;",
            "    result->ch9_program = 0u;",
            "    result->ch9_volume = 0u;",
            "    result->ch9_pitch_bend = 0u;",
            "    result->ch9_last_note = 0u;",
            "    result->ch9_last_velocity = 0u;",
            "    result->ch9_active_note_count = 0u;",
            "    result->ch9_active_bitmap_byte = 0u;",
            "}",
            "",
            "int srk_saturn_midi_68k_resident_state_verify(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT *result)",
            "{",
            "    unsigned long index;",
            "    unsigned short actual;",
            "    if(!result) return 0;",
            "    result->status = SRK_MIDI_68K_STATE_VERIFY_NOT_RUN;",
            "    result->mismatch_index = 0u;",
            "    result->expected_value = 0u;",
            "    result->actual_value = 0u;",
            "    srk_midi_68k_state_fill_snapshot(result);",
            "    for(index=0UL; index<(unsigned long)(sizeof(srk_midi_68k_expected_summary_words) / sizeof(srk_midi_68k_expected_summary_words[0])); index++){",
            "        actual = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_SUMMARY_ADDRESS + (index * 2UL));",
            "        if(actual != srk_midi_68k_expected_summary_words[index]){",
            "            result->status = SRK_MIDI_68K_STATE_VERIFY_SUMMARY_MISMATCH;",
            "            result->mismatch_index = (unsigned short)index;",
            "            result->expected_value = srk_midi_68k_expected_summary_words[index];",
            "            result->actual_value = actual;",
            "            return 0;",
            "        }",
            "    }",
            "    for(index=0UL; index<(unsigned long)(sizeof(srk_midi_68k_expected_controller_words) / sizeof(srk_midi_68k_expected_controller_words[0])); index++){",
            "        actual = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_CONTROLLER_ADDRESS + (index * 2UL));",
            "        if(actual != srk_midi_68k_expected_controller_words[index]){",
            "            result->status = SRK_MIDI_68K_STATE_VERIFY_CONTROLLER_MISMATCH;",
            "            result->mismatch_index = (unsigned short)index;",
            "            result->expected_value = srk_midi_68k_expected_controller_words[index];",
            "            result->actual_value = actual;",
            "            return 0;",
            "        }",
            "    }",
            "    for(index=0UL; index<(unsigned long)(sizeof(srk_midi_68k_expected_active_words) / sizeof(srk_midi_68k_expected_active_words[0])); index++){",
            "        actual = srk_midi_68k_state_read_word(SRK_MIDI_68K_STATE_VERIFY_ACTIVE_ADDRESS + (index * 2UL));",
            "        if(actual != srk_midi_68k_expected_active_words[index]){",
            "            result->status = SRK_MIDI_68K_STATE_VERIFY_ACTIVE_NOTE_MISMATCH;",
            "            result->mismatch_index = (unsigned short)index;",
            "            result->expected_value = srk_midi_68k_expected_active_words[index];",
            "            result->actual_value = actual;",
            "            return 0;",
            "        }",
            "    }",
            "    result->status = SRK_MIDI_68K_STATE_VERIFY_PASS;",
            "    return 1;",
            "}",
            "",
        )
    )
    return "\n".join(lines)
