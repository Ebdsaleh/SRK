"""Physical proof contract for the resident multi-batch/timestamp service.

The proof remains silent.  It drives the compiler-accepted continuous service
through two queue fills (32 + 8 records), advances the producer-published clock
through reviewed milestones, and verifies that the real MC68EC000 does not
execute records early.  Final Sound-RAM MIDI state is compared word-for-word
against the host model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT,
    SATURN_MIDI_68K_CH_PITCH_BEND,
    SATURN_MIDI_68K_CH_PROGRAM,
    SATURN_MIDI_68K_CHANNEL_STATE_BYTES,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_STATE_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
)
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
    build_srk_saturn_midi_stream_batches,
    simulate_srk_saturn_midi_stream_timeline,
)
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS = 40
SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS = 32
SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS = 8
SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_0_US = 0
SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US = 15000
SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US = 32000
SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US = 40000
SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL = 3
SATURN_MIDI_68K_STREAM_PHYSICAL_CONTROLLER = 74

SATURN_MIDI_68K_STREAM_VERIFY_NOT_RUN = 0
SATURN_MIDI_68K_STREAM_VERIFY_PASS = 1
SATURN_MIDI_68K_STREAM_VERIFY_SUMMARY_MISMATCH = 2
SATURN_MIDI_68K_STREAM_VERIFY_CONTROLLER_MISMATCH = 3
SATURN_MIDI_68K_STREAM_VERIFY_ACTIVE_NOTE_MISMATCH = 4

SATURN_MIDI_68K_STREAM_PHASE_NOT_STARTED = 0
SATURN_MIDI_68K_STREAM_PHASE_WAIT_BOOT = 1
SATURN_MIDI_68K_STREAM_PHASE_WAIT_ZERO = 2
SATURN_MIDI_68K_STREAM_PHASE_WAIT_PARTIAL = 3
SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH1_ACK = 4
SATURN_MIDI_68K_STREAM_PHASE_WAIT_REFILL = 5
SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH2_ACK = 6
SATURN_MIDI_68K_STREAM_PHASE_VERIFY_STATE = 7
SATURN_MIDI_68K_STREAM_PHASE_PASS = 8
SATURN_MIDI_68K_STREAM_PHASE_ERROR = 9


@dataclass(frozen=True)
class SaturnMidi68KStreamPhysicalSnapshot:
    cc74: int
    program: int
    pitch_bend: int
    active_note_count: int
    final_note: int
    final_velocity: int
    total_records: int
    batches: int


def build_srk_saturn_midi_68k_stream_physical_program() -> SaturnMidiProgram:
    """Return the reviewed 32+8 physical stream/scheduler proof program."""

    ch = SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL
    records = [
        SaturnMidiRecord(
            (index + 1) * 1000,
            SaturnMidiOpcode.CONTROL_CHANGE,
            ch,
            SATURN_MIDI_68K_STREAM_PHYSICAL_CONTROLLER,
            index,
        )
        for index in range(32)
    ]
    records.extend(
        (
            SaturnMidiRecord(33000, SaturnMidiOpcode.PROGRAM_CHANGE, ch, 12, 0),
            SaturnMidiRecord(34000, SaturnMidiOpcode.NOTE_ON, ch, 64, 100),
            SaturnMidiRecord(35000, SaturnMidiOpcode.PITCH_BEND, ch, 52, 78),
            SaturnMidiRecord(36000, SaturnMidiOpcode.CONTROL_CHANGE, ch, 7, 91),
            SaturnMidiRecord(37000, SaturnMidiOpcode.CHANNEL_PRESSURE, ch, 70, 0),
            SaturnMidiRecord(38000, SaturnMidiOpcode.POLY_AFTERTOUCH, ch, 64, 55),
            SaturnMidiRecord(39000, SaturnMidiOpcode.NOTE_OFF, ch, 64, 32),
            SaturnMidiRecord(40000, SaturnMidiOpcode.NOTE_ON, ch, 67, 88),
        )
    )
    program = SaturnMidiProgram(
        records=tuple(records),
        duration_us=SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
    )
    batches = build_srk_saturn_midi_stream_batches(program)
    if len(program.records) != SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS:
        raise RuntimeError("stream physical proof record count changed")
    if tuple(len(batch.records) for batch in batches) != (
        SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
        SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
    ):
        raise RuntimeError("stream physical proof must remain a 32+8 refill")
    if tuple(batch.sequence for batch in batches) != (1, 2):
        raise RuntimeError("stream physical proof sequence contract changed")
    if set(record.opcode for record in program.records) != set(SaturnMidiOpcode):
        raise RuntimeError("stream physical proof must exercise every SRKM v1 opcode")
    return program


def build_srk_saturn_midi_68k_stream_physical_snapshot() -> SaturnMidi68KStreamPhysicalSnapshot:
    program = build_srk_saturn_midi_68k_stream_physical_program()
    final = simulate_srk_saturn_midi_stream_timeline(
        program, (SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,)
    )[-1]
    channel = final.channels[SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL]
    return SaturnMidi68KStreamPhysicalSnapshot(
        cc74=channel.controllers[SATURN_MIDI_68K_STREAM_PHYSICAL_CONTROLLER],
        program=channel.program,
        pitch_bend=channel.pitch_bend,
        active_note_count=channel.active_note_count,
        final_note=channel.last_note,
        final_velocity=channel.last_velocity,
        total_records=final.total_processed_records,
        batches=final.batch_count,
    )


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise RuntimeError("stream physical proof payload is not word aligned")
    return tuple(
        (payload[index] << 8) | payload[index + 1]
        for index in range(0, len(payload), 2)
    )


def build_srk_saturn_midi_68k_stream_expected_words() -> tuple[
    tuple[int, ...], tuple[int, ...], tuple[int, ...]
]:
    final = simulate_srk_saturn_midi_stream_timeline(
        build_srk_saturn_midi_68k_stream_physical_program(),
        (SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,),
    )[-1]
    return (
        pack_srk_saturn_midi_68k_state_words(final),
        _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(final)),
        _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(final)),
    )


def _render_events(name: str, records: tuple[SaturnMidiRecord, ...]) -> list[str]:
    lines = [f"static const SRK_SATURN_MIDI_EVENT {name}[] = {{"]
    for record in records:
        lines.append(
            "    {"
            f"{record.time_us}UL, "
            f"{int(record.opcode)}u, "
            f"{record.channel}u, "
            f"{record.data0}u, "
            f"{record.data1}u"
            "},"
        )
    lines.extend(("};", ""))
    return lines


def _render_words(name: str, words: tuple[int, ...]) -> list[str]:
    lines = [f"static const unsigned short {name}[] = {{"]
    for offset in range(0, len(words), 8):
        lines.append(
            "    "
            + ", ".join(f"0x{word:04X}u" for word in words[offset : offset + 8])
            + ","
        )
    lines.extend(("};", ""))
    return lines


def render_srk_saturn_midi_68k_stream_physical_proof_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "    unsigned short phase;",
            "    unsigned short stream_flags;",
            "    unsigned short current_index;",
            "    unsigned short batch_count;",
            "    unsigned short total_processed;",
            "    unsigned short wait_zero_pass;",
            "    unsigned short partial_15ms_pass;",
            "    unsigned short batch1_ack_pass;",
            "    unsigned short refill_wait_pass;",
            "    unsigned short batch2_ack_pass;",
            "    unsigned short state_verify_status;",
            "    unsigned short mismatch_region;",
            "    unsigned short mismatch_index;",
            "    unsigned short expected_value;",
            "    unsigned short actual_value;",
            "    unsigned short final_cc74;",
            "    unsigned short final_program;",
            "    unsigned short final_pitch;",
            "    unsigned short final_active;",
            "} SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_TELEMETRY;",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_TELEMETRY telemetry;",
            "} SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_stream_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_stream_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_stream_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_stream_physical_proof_source() -> str:
    program = build_srk_saturn_midi_68k_stream_physical_program()
    batches = build_srk_saturn_midi_stream_batches(program)
    summaries, controllers, active = build_srk_saturn_midi_68k_stream_expected_words()
    snapshot = build_srk_saturn_midi_68k_stream_physical_snapshot()

    summary_program_address = (
        SATURN_MIDI_68K_STATE_ADDRESS
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
        + SATURN_MIDI_68K_CH_PROGRAM
    )
    summary_pitch_address = (
        SATURN_MIDI_68K_STATE_ADDRESS
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
        + SATURN_MIDI_68K_CH_PITCH_BEND
    )
    summary_active_address = (
        SATURN_MIDI_68K_STATE_ADDRESS
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
        + SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT
    )
    cc74_address = (
        SATURN_MIDI_68K_CONTROLLER_ADDRESS
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CHANNEL * 128
        + SATURN_MIDI_68K_STREAM_PHYSICAL_CONTROLLER
    )

    lines = [
        '#include "srk_saturn_midi_68k_stream_physical_proof.h"',
        '#include "srk_saturn_midi_68k_hardware_adapter.h"',
        '#include "srk_saturn_midi_68k_installer.h"',
        '#include "srk_saturn_midi_68k_resident_stream_service.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_STREAM_PROOF_RAM ((volatile unsigned short *)0x25A00000UL)",
        f"#define SRK_STREAM_PROOF_SERVICE 0x{SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS:08X}UL",
        f"#define SRK_STREAM_PROOF_SERVICE_MAGIC_OFFSET {SATURN_MIDI_68K_STREAM_MAGIC_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_SERVICE_VERSION_OFFSET {SATURN_MIDI_68K_STREAM_VERSION_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_SERVICE_FLAGS_OFFSET {SATURN_MIDI_68K_STREAM_FLAGS_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_CURRENT_INDEX_OFFSET {SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_BATCH_COUNT_OFFSET {SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_TOTAL_HI_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_TOTAL_LO_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_LAST_ERROR_OFFSET {SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET}UL",
        f"#define SRK_STREAM_PROOF_SERVICE_MAGIC 0x{SATURN_MIDI_68K_STREAM_SERVICE_MAGIC:04X}u",
        f"#define SRK_STREAM_PROOF_SERVICE_VERSION {SATURN_MIDI_68K_STREAM_SERVICE_VERSION}u",
        f"#define SRK_STREAM_PROOF_WAIT_BATCH 0x{SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH:04X}u",
        f"#define SRK_STREAM_PROOF_WAIT_TIME 0x{SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME:04X}u",
        f"#define SRK_STREAM_PROOF_ERROR 0x{SATURN_MIDI_68K_STREAM_FLAG_ERROR:04X}u",
        f"#define SRK_STREAM_PROOF_SUMMARY_ADDRESS 0x{SATURN_MIDI_68K_STATE_ADDRESS:08X}UL",
        f"#define SRK_STREAM_PROOF_CONTROLLER_ADDRESS 0x{SATURN_MIDI_68K_CONTROLLER_ADDRESS:08X}UL",
        f"#define SRK_STREAM_PROOF_ACTIVE_ADDRESS 0x{SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:08X}UL",
        f"#define SRK_STREAM_PROOF_PROGRAM_ADDRESS 0x{summary_program_address:08X}UL",
        f"#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x{summary_pitch_address:08X}UL",
        f"#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x{summary_active_address:08X}UL",
        f"#define SRK_STREAM_PROOF_CC74_ADDRESS 0x{cc74_address:08X}UL",
        "",
    ]
    lines.extend(_render_events("srk_stream_proof_batch1", batches[0].records))
    lines.extend(_render_events("srk_stream_proof_batch2", batches[1].records))
    lines.extend(_render_words("srk_stream_proof_expected_summary", summaries))
    lines.extend(_render_words("srk_stream_proof_expected_controllers", controllers))
    lines.extend(_render_words("srk_stream_proof_expected_active", active))
    lines.extend(
        (
            "static unsigned short srk_stream_proof_read(unsigned long address)",
            "{",
            "    return SRK_STREAM_PROOF_RAM[address >> 1];",
            "}",
            "",
            "static void srk_stream_proof_write(unsigned long address, unsigned short value)",
            "{",
            "    SRK_STREAM_PROOF_RAM[address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_stream_proof_service(unsigned long offset)",
            "{",
            "    return srk_stream_proof_read(SRK_STREAM_PROOF_SERVICE + offset);",
            "}",
            "",
            "static unsigned short srk_stream_proof_mailbox(unsigned long word_index)",
            "{",
            "    return srk_stream_proof_read(SRK_MIDI_MAILBOX_ADDRESS + (word_index * 2UL));",
            "}",
            "",
            "static int srk_stream_proof_install(void)",
            "{",
            "    unsigned long index;",
            "    for(index=0UL; index<0x0100UL; index+=2UL)",
            "        srk_stream_proof_write(SRK_MIDI_MAILBOX_ADDRESS + index, 0u);",
            "    for(index=0UL; index<0x0200UL; index+=2UL)",
            "        srk_stream_proof_write(SRK_STREAM_PROOF_SERVICE + index, 0u);",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_WORD_COUNT; index++)",
            "        srk_stream_proof_write(",
            "            SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_resident_stream_service_program[index]);",
            "    srk_stream_proof_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS >> 16));",
            "    srk_stream_proof_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_STREAM_STACK_ADDRESS & 0xFFFFUL));",
            "    srk_stream_proof_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS >> 16));",
            "    srk_stream_proof_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS & 0xFFFFUL));",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_stream_proof_read(SRK_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_resident_stream_service_program[index]) return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static void srk_stream_proof_capture(SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short total_hi;",
            "    state->telemetry.flags = srk_stream_proof_mailbox(SRK_MIDI_MB_FLAGS);",
            "    state->telemetry.read_sequence = srk_stream_proof_mailbox(SRK_MIDI_MB_READ_SEQUENCE);",
            "    state->telemetry.read_index = srk_stream_proof_mailbox(SRK_MIDI_MB_READ_INDEX);",
            "    state->telemetry.last_error = srk_stream_proof_mailbox(SRK_MIDI_MB_LAST_ERROR);",
            "    state->telemetry.stream_flags = srk_stream_proof_service(SRK_STREAM_PROOF_SERVICE_FLAGS_OFFSET);",
            "    state->telemetry.current_index = srk_stream_proof_service(SRK_STREAM_PROOF_CURRENT_INDEX_OFFSET);",
            "    state->telemetry.batch_count = srk_stream_proof_service(SRK_STREAM_PROOF_BATCH_COUNT_OFFSET);",
            "    total_hi = srk_stream_proof_service(SRK_STREAM_PROOF_TOTAL_HI_OFFSET);",
            "    state->telemetry.total_processed = srk_stream_proof_service(SRK_STREAM_PROOF_TOTAL_LO_OFFSET);",
            "    if(total_hi != 0u) state->telemetry.total_processed = 0xFFFFu;",
            "    state->telemetry.final_cc74 = (unsigned short)(SRK_STREAM_PROOF_RAM[SRK_STREAM_PROOF_CC74_ADDRESS >> 1] >> 8);",
            "    state->telemetry.final_program = srk_stream_proof_read(SRK_STREAM_PROOF_PROGRAM_ADDRESS);",
            "    state->telemetry.final_pitch = srk_stream_proof_read(SRK_STREAM_PROOF_PITCH_ADDRESS);",
            "    state->telemetry.final_active = srk_stream_proof_read(SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS);",
            "}",
            "",
            "static int srk_stream_proof_verify_region(",
            "    unsigned long address, const unsigned short *expected, unsigned short count,",
            "    unsigned short region, SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short index;",
            "    unsigned short actual;",
            "    for(index=0u; index<count; index++){",
            "        actual = srk_stream_proof_read(address + ((unsigned long)index * 2UL));",
            "        if(actual != expected[index]){",
            "            state->telemetry.state_verify_status = region;",
            "            state->telemetry.mismatch_region = region;",
            "            state->telemetry.mismatch_index = index;",
            "            state->telemetry.expected_value = expected[index];",
            "            state->telemetry.actual_value = actual;",
            "            return 0;",
            "        }",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_stream_proof_verify_state(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            f"    if(!srk_stream_proof_verify_region(SRK_STREAM_PROOF_SUMMARY_ADDRESS, srk_stream_proof_expected_summary, {len(summaries)}u, {SATURN_MIDI_68K_STREAM_VERIFY_SUMMARY_MISMATCH}u, state)) return 0;",
            f"    if(!srk_stream_proof_verify_region(SRK_STREAM_PROOF_CONTROLLER_ADDRESS, srk_stream_proof_expected_controllers, {len(controllers)}u, {SATURN_MIDI_68K_STREAM_VERIFY_CONTROLLER_MISMATCH}u, state)) return 0;",
            f"    if(!srk_stream_proof_verify_region(SRK_STREAM_PROOF_ACTIVE_ADDRESS, srk_stream_proof_expected_active, {len(active)}u, {SATURN_MIDI_68K_STREAM_VERIFY_ACTIVE_NOTE_MISMATCH}u, state)) return 0;",
            f"    state->telemetry.state_verify_status = {SATURN_MIDI_68K_STREAM_VERIFY_PASS}u;",
            "    return 1;",
            "}",
            "",
            "static unsigned int srk_stream_proof_fail(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state, unsigned short code)",
            "{",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_ERROR}u;",
            "    if(state->telemetry.last_error == 0u) state->telemetry.last_error = code;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    return state->runtime_status;",
            "}",
            "",
            "void srk_saturn_midi_68k_stream_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short *words;",
            "    unsigned long count;",
            "    if(!state) return;",
            "    words = (unsigned short *)&state->telemetry;",
            "    count = (unsigned long)(sizeof(state->telemetry) / sizeof(unsigned short));",
            "    while(count) words[--count] = 0u;",
            "    state->attempted = 0u;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    state->poll_count = 0u;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_NOT_STARTED}u;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_stream_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops;",
            "    if(!state) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted) return state->runtime_status;",
            "    state->attempted = 1u;",
            "    ops = srk_saturn_midi_68k_hardware_adapter_ops();",
            "    if(!ops || !ops->stop_sound_cpu || !ops->start_sound_cpu)",
            "        return srk_stream_proof_fail(state, 0xE001u);",
            "    if(!ops->stop_sound_cpu()) return srk_stream_proof_fail(state, 0xE002u);",
            "    if(!srk_stream_proof_install()) return srk_stream_proof_fail(state, 0xE003u);",
            "    if(!ops->start_sound_cpu()) return srk_stream_proof_fail(state, 0xE004u);",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_RUNNING;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BOOT}u;",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_stream_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short phase;",
            "    if(!state || !state->attempted) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "    state->poll_count += 1u;",
            "    srk_stream_proof_capture(state);",
            "    phase = state->telemetry.phase;",
            "    if((state->telemetry.stream_flags & SRK_STREAM_PROOF_ERROR) != 0u ||",
            "       srk_stream_proof_service(SRK_STREAM_PROOF_LAST_ERROR_OFFSET) != 0u ||",
            "       state->telemetry.last_error != 0u)",
            "        return srk_stream_proof_fail(state, 0xE010u);",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BOOT}u){{",
            "        if(srk_stream_proof_service(SRK_STREAM_PROOF_SERVICE_MAGIC_OFFSET) == SRK_STREAM_PROOF_SERVICE_MAGIC &&",
            "           srk_stream_proof_service(SRK_STREAM_PROOF_SERVICE_VERSION_OFFSET) == SRK_STREAM_PROOF_SERVICE_VERSION &&",
            "           state->telemetry.stream_flags == SRK_STREAM_PROOF_WAIT_BATCH){",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_0_US}UL);",
            f"            if(!srk_saturn_midi_stream_batch_publish(srk_stream_proof_batch1, {SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS}u, 1u))",
            "                return srk_stream_proof_fail(state, 0xE011u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_ZERO}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_ZERO}u){{",
            "        if(state->telemetry.stream_flags == SRK_STREAM_PROOF_WAIT_TIME &&",
            "           state->telemetry.current_index == 0u && state->telemetry.read_sequence == 0u){",
            "            state->telemetry.wait_zero_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_PARTIAL}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_PARTIAL}u){{",
            "        if(state->telemetry.stream_flags == SRK_STREAM_PROOF_WAIT_TIME &&",
            "           state->telemetry.current_index == 15u && state->telemetry.read_sequence == 0u &&",
            "           state->telemetry.total_processed == 15u){",
            "            state->telemetry.partial_15ms_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH1_ACK}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH1_ACK}u){{",
            "        if(state->telemetry.read_sequence == 1u && state->telemetry.read_index == 32u &&",
            "           state->telemetry.batch_count == 1u && state->telemetry.total_processed == 32u){",
            "            state->telemetry.batch1_ack_pass = 1u;",
            f"            if(!srk_saturn_midi_stream_batch_publish(srk_stream_proof_batch2, {SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS}u, 2u))",
            "                return srk_stream_proof_fail(state, 0xE012u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_REFILL}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_REFILL}u){{",
            "        if(state->telemetry.stream_flags == SRK_STREAM_PROOF_WAIT_TIME &&",
            "           state->telemetry.current_index == 0u && state->telemetry.read_sequence == 1u &&",
            "           state->telemetry.total_processed == 32u){",
            "            state->telemetry.refill_wait_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH2_ACK}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_WAIT_BATCH2_ACK}u){{",
            "        if(state->telemetry.read_sequence == 2u && state->telemetry.read_index == 8u &&",
            "           state->telemetry.batch_count == 2u && state->telemetry.total_processed == 40u){",
            "            state->telemetry.batch2_ack_pass = 1u;",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_VERIFY_STATE}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_STREAM_PHASE_VERIFY_STATE}u){{",
            "        if(!srk_stream_proof_verify_state(state))",
            "            return srk_stream_proof_fail(state, 0xE013u);",
            "        srk_stream_proof_capture(state);",
            f"        if(state->telemetry.final_cc74 != {snapshot.cc74}u ||",
            f"           state->telemetry.final_program != {snapshot.program}u ||",
            f"           state->telemetry.final_pitch != {snapshot.pitch_bend}u ||",
            f"           state->telemetry.final_active != {snapshot.active_note_count}u)",
            "            return srk_stream_proof_fail(state, 0xE014u);",
            f"        state->telemetry.phase = {SATURN_MIDI_68K_STREAM_PHASE_PASS}u;",
            "        state->runtime_status = SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;",
            "        return state->runtime_status;",
            "    }",
            "",
            "    return state->runtime_status;",
            "}",
            "",
        )
    )
    return "\n".join(lines)


_STREAM_DEFINE = "#define SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE 1"
_STATE_DEFINE = "#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE 1"
_STATE_MENU_LABEL = '"MIDI 68K State Proof"'
_STREAM_MENU_LABEL = '"MIDI 68K Stream Proof"'
_C_BACKSLASH = chr(92)
_STATE_GUARD = (
    "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE) || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)"
)
_STREAM_GUARD = (
    _STATE_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE)"
)


def derive_resident_stream_candidate_main(state_main: str) -> str:
    """Transform only a copied R21 state-candidate main into the stream proof."""

    if not state_main.startswith(_STATE_DEFINE + "\n"):
        raise RuntimeError("R21 main no longer begins with the accepted state candidate define")
    main = _STREAM_DEFINE + state_main[len(_STATE_DEFINE):]

    if main.count(_STATE_GUARD) < 2:
        raise RuntimeError("R21 proof preprocessor guard shape changed")
    main = main.replace(_STATE_GUARD, _STREAM_GUARD)

    state_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_resident_state_physical_proof.h"',
            "#endif",
        )
    )
    if main.count(state_include) != 1:
        raise RuntimeError("R21 state proof include block shape changed")
    main = main.replace(
        state_include,
        state_include
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE\n"
        + '#include "srk_saturn_midi_68k_stream_physical_proof.h"\n'
        + "#endif",
        1,
    )

    state_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_RESIDENT_STATE_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K STATE PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "20 records - full MIDI state verify"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "State PASS: full MIDI state matched"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_resident_state_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_resident_state_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_resident_state_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(state_alias) != 1:
        raise RuntimeError("R21 state proof alias block shape changed")
    stream_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_STREAM_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 8u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K STREAM PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "32+8 refill - timestamp scheduler"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Stream PASS: refill + timing + state"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_stream_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_stream_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_stream_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    main = main.replace(state_alias, stream_alias + "\n" + state_alias.split("\n", 1)[1], 1)

    last_error_block = "\n".join(
        (
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);",
            '    srk_midi_68k_draw_field(2, 11, 14, "Last error:");',
            "    srk_midi_68k_draw_field(16, 11, 10, number);",
        )
    )
    if main.count(last_error_block) != 1:
        raise RuntimeError("R21 telemetry rendering shape changed")
    stream_lines = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.phase);",
            '    srk_midi_68k_draw_field(2, 12, 14, "Phase:");',
            "    srk_midi_68k_draw_field(16, 12, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.stream_flags);",
            '    srk_midi_68k_draw_field(2, 13, 14, "Stream flags:");',
            "    srk_midi_68k_draw_field(16, 13, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.current_index);",
            '    srk_midi_68k_draw_field(2, 14, 14, "Current index:");',
            "    srk_midi_68k_draw_field(16, 14, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch_count);",
            '    srk_midi_68k_draw_field(2, 15, 14, "Batch count:");',
            "    srk_midi_68k_draw_field(16, 15, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.total_processed);",
            '    srk_midi_68k_draw_field(2, 16, 14, "Total records:");',
            "    srk_midi_68k_draw_field(16, 16, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.wait_zero_pass);",
            '    srk_midi_68k_draw_field(2, 17, 14, "Wait @ 0us:");',
            "    srk_midi_68k_draw_field(16, 17, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.partial_15ms_pass);",
            '    srk_midi_68k_draw_field(2, 18, 14, "15ms = 15:");',
            "    srk_midi_68k_draw_field(16, 18, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch1_ack_pass);",
            '    srk_midi_68k_draw_field(2, 19, 14, "Batch1 ACK:");',
            "    srk_midi_68k_draw_field(16, 19, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.refill_wait_pass);",
            '    srk_midi_68k_draw_field(2, 20, 14, "Refill wait:");',
            "    srk_midi_68k_draw_field(16, 20, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch2_ack_pass);",
            '    srk_midi_68k_draw_field(2, 21, 14, "Batch2 ACK:");',
            "    srk_midi_68k_draw_field(16, 21, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify_status);",
            '    srk_midi_68k_draw_field(2, 22, 14, "State verify:");',
            "    srk_midi_68k_draw_field(16, 22, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.final_cc74);",
            '    srk_midi_68k_draw_field(2, 23, 6, "CC74:");',
            "    srk_midi_68k_draw_field(8, 23, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.final_program);",
            '    srk_midi_68k_draw_field(15, 23, 6, "Prog:");',
            "    srk_midi_68k_draw_field(21, 23, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.final_pitch);",
            '    srk_midi_68k_draw_field(2, 24, 14, "Final pitch:");',
            "    srk_midi_68k_draw_field(16, 24, 10, number);",
            "#endif",
        )
    )
    main = main.replace(last_error_block, last_error_block + "\n\n" + stream_lines, 1)

    state_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(state_success) != 1:
        raise RuntimeError("R21 success rendering shape changed")
    main = main.replace(
        state_success,
        "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE\n"
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)\n"
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        "#elif defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)",
        1,
    )

    required = (
        _STREAM_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 8u",
        '"MIDI / 68K STREAM PROOF"',
        '"Stream PASS: refill + timing + state"',
        "srk_saturn_midi_68k_stream_physical_proof_begin",
        "telemetry.partial_15ms_pass",
        "telemetry.refill_wait_pass",
        "telemetry.final_pitch",
    )
    for marker in required:
        if marker not in main:
            raise RuntimeError(f"derived stream candidate main missing marker: {marker}")
    return main


def derive_resident_stream_candidate_menu(state_menu: str) -> str:
    if state_menu.count(_STATE_MENU_LABEL) != 1:
        raise RuntimeError("R21 state proof menu label is no longer isolated")
    menu = state_menu.replace(_STATE_MENU_LABEL, _STREAM_MENU_LABEL, 1)
    if menu.count(_STREAM_MENU_LABEL) != 1:
        raise RuntimeError("stream proof menu label derivation failed")
    return menu
