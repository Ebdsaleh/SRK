"""Render the Phase-B physical binding seams for full state verification.

These renderers remain host-side only.  They install the already compiler-
accepted Phase-B MC68EC000 image into a fresh candidate tree, publish the
reviewed 20-record proof program, and require a complete post-execution state
match before the proof can return ACKNOWLEDGED.
"""

from __future__ import annotations

from .midi_68k_resident_state_decoder import (
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION,
)
from .midi_68k_resident_state_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS,
)


def render_resident_state_decoder_installer_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_INSTALLER_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_INSTALLER_H",
            "",
            "/* Caller precondition: MC68EC000 is stopped. This API never launches it. */",
            "int srk_saturn_midi_68k_resident_state_decoder_install_while_stopped(void);",
            "int srk_saturn_midi_68k_resident_state_decoder_verify_install(void);",
            "",
            "#endif",
            "",
        )
    )


def render_resident_state_decoder_installer_source() -> str:
    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_resident_state_decoder_installer.h"',
            '#include "srk_saturn_midi_68k_installer.h"',
            '#include "srk_saturn_midi_68k_resident_state_decoder.h"',
            "",
            "#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
            "",
            "static void srk_state_decoder_write_word(unsigned long byte_address, unsigned short value)",
            "{",
            "    SRK_MIDI_68K_RESIDENT_STATE_DECODER_SOUND_RAM[byte_address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_state_decoder_read_word(unsigned long byte_address)",
            "{",
            "    return SRK_MIDI_68K_RESIDENT_STATE_DECODER_SOUND_RAM[byte_address >> 1];",
            "}",
            "",
            "static void srk_state_decoder_write_long(unsigned long byte_address, unsigned long value)",
            "{",
            "    srk_state_decoder_write_word(byte_address, (unsigned short)(value >> 16));",
            "    srk_state_decoder_write_word(byte_address + 2UL, (unsigned short)(value & 0xFFFFUL));",
            "}",
            "",
            "static unsigned long srk_state_decoder_read_long(unsigned long byte_address)",
            "{",
            "    unsigned long high_word;",
            "    unsigned long low_word;",
            "    high_word = (unsigned long)srk_state_decoder_read_word(byte_address);",
            "    low_word = (unsigned long)srk_state_decoder_read_word(byte_address + 2UL);",
            "    return (high_word << 16) | low_word;",
            "}",
            "",
            "int srk_saturn_midi_68k_resident_state_decoder_verify_install(void)",
            "{",
            "    unsigned long index;",
            "    if(srk_state_decoder_read_long(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS) !=",
            "       SRK_MIDI_68K_RESIDENT_STATE_DECODER_STACK_ADDRESS) return 0;",
            "    if(srk_state_decoder_read_long(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS) !=",
            "       SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS) return 0;",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_state_decoder_read_word(",
            "            SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_resident_state_decoder_program[index]) return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "int srk_saturn_midi_68k_resident_state_decoder_install_while_stopped(void)",
            "{",
            "    unsigned long index;",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_WORD_COUNT; index++)",
            "        srk_state_decoder_write_word(",
            "            SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_resident_state_decoder_program[index]);",
            "    srk_state_decoder_write_long(",
            "        SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        SRK_MIDI_68K_RESIDENT_STATE_DECODER_STACK_ADDRESS);",
            "    srk_state_decoder_write_long(",
            "        SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS);",
            "    return srk_saturn_midi_68k_resident_state_decoder_verify_install();",
            "}",
            "",
        )
    )


def render_resident_state_decoder_runtime_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_RUNTIME_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_DECODER_RUNTIME_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_68k_resident_state_verifier.h"',
            "",
            "#define SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_ADDRESS 0x00001D00UL",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_MAGIC 0x{SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_MAGIC:04X}u",
            f"#define SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_VERSION {SATURN_MIDI_68K_RESIDENT_STATE_DECODER_TELEMETRY_VERSION}u",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "    unsigned short decoder_magic;",
            "    unsigned short decoder_version;",
            "    unsigned short processed;",
            "    unsigned short current_record;",
            "    unsigned short final_time_hi;",
            "    unsigned short final_time_lo;",
            "    unsigned short decoder_ready;",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_VERIFY_RESULT state_verify;",
            "} SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY;",
            "",
            "unsigned int srk_saturn_midi_68k_resident_state_protocol_begin(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops);",
            "unsigned int srk_saturn_midi_68k_resident_state_protocol_poll(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY *telemetry);",
            "",
            "#endif",
            "",
        )
    )


def render_resident_state_decoder_runtime_source() -> str:
    final_hi = (SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US >> 16) & 0xFFFF
    final_lo = SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US & 0xFFFF
    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_resident_state_decoder_runtime.h"',
            '#include "srk_saturn_midi_68k_resident_state_decoder_installer.h"',
            '#include "srk_saturn_midi_68k_resident_state_proof_preload.h"',
            '#include "srk_saturn_midi_mailbox.h"',
            "",
            "#define SRK_MIDI_68K_RESIDENT_STATE_RUNTIME_SOUND_RAM ((volatile unsigned short *)0x25A00000UL)",
            "",
            "static int srk_state_runtime_ops_valid(const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops)",
            "{",
            "    return ops && ops->stop_sound_cpu && ops->start_sound_cpu && ops->read_mailbox_word;",
            "}",
            "",
            "static unsigned short srk_state_runtime_read_telemetry(unsigned long byte_offset)",
            "{",
            "    return SRK_MIDI_68K_RESIDENT_STATE_RUNTIME_SOUND_RAM[",
            "        (SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_ADDRESS + byte_offset) >> 1];",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_resident_state_protocol_begin(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops)",
            "{",
            "    if(!srk_state_runtime_ops_valid(ops)) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(!ops->stop_sound_cpu()) return SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED;",
            "    if(!srk_saturn_midi_68k_resident_state_decoder_install_while_stopped())",
            "        return SRK_MIDI_68K_RUNTIME_INSTALL_FAILED;",
            "    srk_saturn_midi_68k_resident_state_proof_preload_publish();",
            "    if(!srk_saturn_midi_68k_resident_state_proof_preload_verify())",
            "        return SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED;",
            "    if(!ops->start_sound_cpu()) return SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED;",
            "    return SRK_MIDI_68K_RUNTIME_RUNNING;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_resident_state_protocol_poll(",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY *telemetry)",
            "{",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY current;",
            "    if(!srk_state_runtime_ops_valid(ops)) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    srk_saturn_midi_68k_resident_state_verify_reset(&current.state_verify);",
            "    current.flags = ops->read_mailbox_word(SRK_MIDI_MB_FLAGS);",
            "    current.read_sequence = ops->read_mailbox_word(SRK_MIDI_MB_READ_SEQUENCE);",
            "    current.read_index = ops->read_mailbox_word(SRK_MIDI_MB_READ_INDEX);",
            "    current.last_error = ops->read_mailbox_word(SRK_MIDI_MB_LAST_ERROR);",
            "    current.decoder_magic = srk_state_runtime_read_telemetry(0UL);",
            "    current.decoder_version = srk_state_runtime_read_telemetry(2UL);",
            "    current.processed = srk_state_runtime_read_telemetry(4UL);",
            "    current.current_record = srk_state_runtime_read_telemetry(6UL);",
            "    current.final_time_hi = srk_state_runtime_read_telemetry(8UL);",
            "    current.final_time_lo = srk_state_runtime_read_telemetry(10UL);",
            "    current.decoder_ready = srk_state_runtime_read_telemetry(12UL);",
            "    if(current.last_error != 0u){",
            "        if(telemetry) *telemetry = current;",
            "        return SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    }",
            "    if((current.flags & SRK_MIDI_MAILBOX_FLAG_READY) != 0u &&",
            "       current.read_sequence == SRK_MIDI_PRELOAD_WRITE_SEQUENCE &&",
            f"       current.read_index == {SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS}u &&",
            "       current.decoder_magic == SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_MAGIC &&",
            "       current.decoder_version == SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_VERSION &&",
            f"       current.processed == {SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS}u &&",
            f"       current.current_record == {SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS}u &&",
            f"       current.final_time_hi == {final_hi}u &&",
            f"       current.final_time_lo == {final_lo}u &&",
            "       current.decoder_ready == 1u){",
            "        if(!srk_saturn_midi_68k_resident_state_verify(&current.state_verify)){",
            "            if(telemetry) *telemetry = current;",
            "            return SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "        }",
            "        if(telemetry) *telemetry = current;",
            "        return SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;",
            "    }",
            "    if(telemetry) *telemetry = current;",
            "    return SRK_MIDI_68K_RUNTIME_RUNNING;",
            "}",
            "",
        )
    )


def render_resident_state_decoder_proof_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_resident_state_decoder_runtime.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_TELEMETRY telemetry;",
            "} SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_resident_state_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_resident_state_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_resident_state_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_resident_state_decoder_proof_source() -> str:
    fields = (
        "status", "mismatch_index", "expected_value", "actual_value",
        "ch3_program", "ch3_bank_msb", "ch3_bank_lsb", "ch3_volume",
        "ch3_pan", "ch3_expression", "ch3_sustain", "ch3_channel_pressure",
        "ch3_pitch_bend", "ch3_last_note", "ch3_last_velocity",
        "ch3_last_poly_note", "ch3_last_poly_pressure", "ch3_active_note_count",
        "ch3_event_count", "ch3_last_opcode", "ch3_cc74", "ch3_active_bitmap_byte",
        "ch9_program", "ch9_volume", "ch9_pitch_bend", "ch9_last_note",
        "ch9_last_velocity", "ch9_active_note_count", "ch9_active_bitmap_byte",
    )
    lines = [
        '#include "srk_saturn_midi_68k_resident_state_physical_proof.h"',
        '#include "srk_saturn_midi_68k_hardware_adapter.h"',
        "",
        "void srk_saturn_midi_68k_resident_state_physical_proof_reset(",
        "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state)",
        "{",
        "    if(!state) return;",
        "    state->attempted = 0u;",
        "    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
        "    state->poll_count = 0u;",
        "    state->telemetry.flags = 0u;",
        "    state->telemetry.read_sequence = 0u;",
        "    state->telemetry.read_index = 0u;",
        "    state->telemetry.last_error = 0u;",
        "    state->telemetry.decoder_magic = 0u;",
        "    state->telemetry.decoder_version = 0u;",
        "    state->telemetry.processed = 0u;",
        "    state->telemetry.current_record = 0u;",
        "    state->telemetry.final_time_hi = 0u;",
        "    state->telemetry.final_time_lo = 0u;",
        "    state->telemetry.decoder_ready = 0u;",
    ]
    for field in fields:
        lines.append(f"    state->telemetry.state_verify.{field} = 0u;")
    lines.extend(
        (
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_resident_state_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    if(!state) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted) return state->runtime_status;",
            "    state->attempted = 1u;",
            "    state->runtime_status = srk_saturn_midi_68k_resident_state_protocol_begin(",
            "        srk_saturn_midi_68k_hardware_adapter_ops());",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_resident_state_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    if(!state || !state->attempted) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "    state->runtime_status = srk_saturn_midi_68k_resident_state_protocol_poll(",
            "        srk_saturn_midi_68k_hardware_adapter_ops(), &state->telemetry);",
            "    state->poll_count += 1u;",
            "    return state->runtime_status;",
            "}",
            "",
        )
    )
    return "\n".join(lines)
