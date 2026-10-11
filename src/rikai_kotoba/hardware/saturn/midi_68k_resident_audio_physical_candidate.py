"""R23 physical proof for the first MIDI-driven SCSP voice on real Saturn.

R22A physically accepted the continuous MC68EC000 queue/refill/timestamp
service.  R23 keeps that exact shape and adds one deliberately bounded audio
surface.  The physical proof below therefore replays a 32-record first batch,
refills with a two-record NOTE_ON/NOTE_OFF batch, verifies the resident voice
state and SH-2-visible SCSP slot-0 registers, holds the note for a visible/audible
number of display polls, and finally compares the complete MIDI state.

The producer clock remains the same explicit SH-2-published contract accepted by
R22A.  The frame/poll hold is only an audible observation window; it is not a
claim that a final hardware-derived microsecond time source has been selected.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT,
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
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
    build_srk_saturn_midi_stream_batches,
    simulate_srk_saturn_midi_stream_timeline,
)
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_HOLD_US,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_SLOT_CONTROL,
    SATURN_MIDI_68K_SCSP_SLOT_MIXER,
    SATURN_MIDI_68K_SCSP_SLOT_PITCH,
    SATURN_MIDI_68K_VOICE_ACTIVE_WORD,
    SATURN_MIDI_68K_VOICE_CHANNEL_WORD,
    SATURN_MIDI_68K_VOICE_GENERATION_WORD,
    SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD,
    SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD,
    SATURN_MIDI_68K_VOICE_MIXER_WORD,
    SATURN_MIDI_68K_VOICE_NOTE_WORD,
    SATURN_MIDI_68K_VOICE_PITCH_WORD,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
    SATURN_MIDI_68K_VOICE_STATE_WORDS,
    SATURN_MIDI_68K_VOICE_VELOCITY_WORD,
    build_srk_saturn_midi_68k_r23_first_note_snapshot,
    pack_srk_saturn_midi_68k_voice_state_words,
)
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_R23_PHYSICAL_RECORDS = 34
SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS = 32
SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS = 2
SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_0_US = 0
SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US = 15000
SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US = 32000
SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US = 33000
SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US = (
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US + SATURN_MIDI_68K_R23_HOLD_US
)
SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS = 60
SATURN_MIDI_68K_R23_PHYSICAL_CONTROLLER = 74

SATURN_MIDI_68K_R23_VERIFY_NOT_RUN = 0
SATURN_MIDI_68K_R23_VERIFY_PASS = 1
SATURN_MIDI_68K_R23_VERIFY_SUMMARY_MISMATCH = 2
SATURN_MIDI_68K_R23_VERIFY_CONTROLLER_MISMATCH = 3
SATURN_MIDI_68K_R23_VERIFY_ACTIVE_NOTE_MISMATCH = 4
SATURN_MIDI_68K_R23_VERIFY_VOICE_MISMATCH = 5
SATURN_MIDI_68K_R23_VERIFY_SCSP_MISMATCH = 6

SATURN_MIDI_68K_R23_PHASE_NOT_STARTED = 0
SATURN_MIDI_68K_R23_PHASE_WAIT_BOOT = 1
SATURN_MIDI_68K_R23_PHASE_WAIT_ZERO = 2
SATURN_MIDI_68K_R23_PHASE_WAIT_PARTIAL = 3
SATURN_MIDI_68K_R23_PHASE_WAIT_BATCH1_ACK = 4
SATURN_MIDI_68K_R23_PHASE_WAIT_REFILL = 5
SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_ON = 6
SATURN_MIDI_68K_R23_PHASE_AUDIBLE_HOLD = 7
SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_OFF = 8
SATURN_MIDI_68K_R23_PHASE_VERIFY_STATE = 9
SATURN_MIDI_68K_R23_PHASE_PASS = 10
SATURN_MIDI_68K_R23_PHASE_ERROR = 11


@dataclass(frozen=True)
class SaturnMidi68KR23PhysicalSnapshot:
    cc74: int
    final_active_note_count: int
    total_records: int
    batches: int
    voice_key_on_count: int
    voice_key_off_count: int


def build_srk_saturn_midi_68k_r23_physical_program() -> SaturnMidiProgram:
    """Return the reviewed R23 32+2 refill/audio physical program."""

    ch = SATURN_MIDI_68K_R23_CHANNEL
    records = [
        SaturnMidiRecord(
            (index + 1) * 1000,
            SaturnMidiOpcode.CONTROL_CHANGE,
            ch,
            SATURN_MIDI_68K_R23_PHYSICAL_CONTROLLER,
            index,
        )
        for index in range(SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS)
    ]
    records.extend(
        (
            SaturnMidiRecord(
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
                SaturnMidiOpcode.NOTE_ON,
                ch,
                SATURN_MIDI_68K_R23_NOTE,
                SATURN_MIDI_68K_R23_VELOCITY,
            ),
            SaturnMidiRecord(
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
                SaturnMidiOpcode.NOTE_OFF,
                ch,
                SATURN_MIDI_68K_R23_NOTE,
                64,
            ),
        )
    )
    program = SaturnMidiProgram(
        records=tuple(records),
        duration_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
    )
    batches = build_srk_saturn_midi_stream_batches(program)
    if len(program.records) != SATURN_MIDI_68K_R23_PHYSICAL_RECORDS:
        raise RuntimeError("R23 physical proof record count changed")
    if tuple(len(batch.records) for batch in batches) != (
        SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
        SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
    ):
        raise RuntimeError("R23 physical proof must remain a 32+2 refill")
    if tuple(batch.sequence for batch in batches) != (1, 2):
        raise RuntimeError("R23 physical proof sequence contract changed")
    return program


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise RuntimeError("R23 physical proof payload is not word aligned")
    return tuple(
        (payload[index] << 8) | payload[index + 1]
        for index in range(0, len(payload), 2)
    )


def build_srk_saturn_midi_68k_r23_expected_midi_words() -> tuple[
    tuple[int, ...], tuple[int, ...], tuple[int, ...]
]:
    final = simulate_srk_saturn_midi_stream_timeline(
        build_srk_saturn_midi_68k_r23_physical_program(),
        (SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,),
    )[-1]
    return (
        pack_srk_saturn_midi_68k_state_words(final),
        _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(final)),
        _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(final)),
    )


def build_srk_saturn_midi_68k_r23_physical_snapshot() -> SaturnMidi68KR23PhysicalSnapshot:
    final = simulate_srk_saturn_midi_stream_timeline(
        build_srk_saturn_midi_68k_r23_physical_program(),
        (SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,),
    )[-1]
    channel = final.channels[SATURN_MIDI_68K_R23_CHANNEL]
    voice = build_srk_saturn_midi_68k_r23_first_note_snapshot().after_note_off
    return SaturnMidi68KR23PhysicalSnapshot(
        cc74=channel.controllers[SATURN_MIDI_68K_R23_PHYSICAL_CONTROLLER],
        final_active_note_count=channel.active_note_count,
        total_records=final.total_processed_records,
        batches=final.batch_count,
        voice_key_on_count=voice.key_on_count,
        voice_key_off_count=voice.key_off_count,
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


def render_srk_saturn_midi_68k_r23_physical_proof_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R23_PHYSICAL_TELEMETRY {",
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
            "    unsigned short key_on_pass;",
            "    unsigned short audible_hold_polls;",
            "    unsigned short key_off_pass;",
            "    unsigned short state_verify_status;",
            "    unsigned short mismatch_region;",
            "    unsigned short mismatch_index;",
            "    unsigned short expected_value;",
            "    unsigned short actual_value;",
            "    unsigned short voice_active;",
            "    unsigned short voice_generation;",
            "    unsigned short voice_note;",
            "    unsigned short voice_velocity;",
            "    unsigned short voice_key_on_count;",
            "    unsigned short voice_key_off_count;",
            "    unsigned short voice_last_error;",
            "    unsigned short voice_pitch;",
            "    unsigned short voice_mixer;",
            "    unsigned short voice_control;",
            "    unsigned short scsp_control;",
            "    unsigned short scsp_pitch;",
            "    unsigned short scsp_mixer;",
            "    unsigned short final_cc74;",
            "} SRK_SATURN_MIDI_68K_R23_PHYSICAL_TELEMETRY;",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_TELEMETRY telemetry;",
            "} SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_r23_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r23_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r23_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r23_physical_proof_source() -> str:
    program = build_srk_saturn_midi_68k_r23_physical_program()
    batches = build_srk_saturn_midi_stream_batches(program)
    summaries, controllers, active = build_srk_saturn_midi_68k_r23_expected_midi_words()
    voice_snapshot = build_srk_saturn_midi_68k_r23_first_note_snapshot()
    voice_on = pack_srk_saturn_midi_68k_voice_state_words(voice_snapshot.after_note_on)
    voice_off = pack_srk_saturn_midi_68k_voice_state_words(voice_snapshot.after_note_off)
    snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()

    active_count_address = (
        SATURN_MIDI_68K_STATE_ADDRESS
        + SATURN_MIDI_68K_R23_CHANNEL * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
        + SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT * 2
    )
    cc74_address = (
        SATURN_MIDI_68K_CONTROLLER_ADDRESS
        + SATURN_MIDI_68K_R23_CHANNEL * 128
        + SATURN_MIDI_68K_R23_PHYSICAL_CONTROLLER
    )
    expected_on = voice_snapshot.after_note_on.owned_slot
    expected_off = voice_snapshot.after_note_off.owned_slot

    lines = [
        '#include "srk_saturn_midi_68k_r23_physical_proof.h"',
        '#include "srk_saturn_midi_68k_hardware_adapter.h"',
        '#include "srk_saturn_midi_68k_installer.h"',
        '#include "srk_saturn_midi_68k_resident_audio_service.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        '#include "srk_saturn_midi_68k_voice_state.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_R23_PROOF_RAM ((volatile unsigned short *)0x25A00000UL)",
        "#define SRK_R23_PROOF_SCSP ((volatile unsigned short *)0x25B00000UL)",
        f"#define SRK_R23_PROOF_SERVICE 0x{SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS:08X}UL",
        f"#define SRK_R23_PROOF_SERVICE_MAGIC_OFFSET {SATURN_MIDI_68K_STREAM_MAGIC_OFFSET}UL",
        f"#define SRK_R23_PROOF_SERVICE_VERSION_OFFSET {SATURN_MIDI_68K_STREAM_VERSION_OFFSET}UL",
        f"#define SRK_R23_PROOF_SERVICE_FLAGS_OFFSET {SATURN_MIDI_68K_STREAM_FLAGS_OFFSET}UL",
        f"#define SRK_R23_PROOF_CURRENT_INDEX_OFFSET {SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET}UL",
        f"#define SRK_R23_PROOF_BATCH_COUNT_OFFSET {SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET}UL",
        f"#define SRK_R23_PROOF_TOTAL_HI_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET}UL",
        f"#define SRK_R23_PROOF_TOTAL_LO_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET}UL",
        f"#define SRK_R23_PROOF_LAST_ERROR_OFFSET {SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET}UL",
        f"#define SRK_R23_PROOF_SERVICE_MAGIC 0x{SATURN_MIDI_68K_STREAM_SERVICE_MAGIC:04X}u",
        f"#define SRK_R23_PROOF_SERVICE_VERSION {SATURN_MIDI_68K_STREAM_SERVICE_VERSION}u",
        f"#define SRK_R23_PROOF_WAIT_BATCH 0x{SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH:04X}u",
        f"#define SRK_R23_PROOF_WAIT_TIME 0x{SATURN_MIDI_68K_STREAM_FLAG_WAIT_TIME:04X}u",
        f"#define SRK_R23_PROOF_ERROR 0x{SATURN_MIDI_68K_STREAM_FLAG_ERROR:04X}u",
        f"#define SRK_R23_PROOF_VOICE_ADDRESS 0x{SATURN_MIDI_68K_VOICE_STATE_ADDRESS:08X}UL",
        f"#define SRK_R23_PROOF_SUMMARY_ADDRESS 0x{SATURN_MIDI_68K_STATE_ADDRESS:08X}UL",
        f"#define SRK_R23_PROOF_CONTROLLER_ADDRESS 0x{SATURN_MIDI_68K_CONTROLLER_ADDRESS:08X}UL",
        f"#define SRK_R23_PROOF_ACTIVE_ADDRESS 0x{SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:08X}UL",
        f"#define SRK_R23_PROOF_ACTIVE_COUNT_ADDRESS 0x{active_count_address:08X}UL",
        f"#define SRK_R23_PROOF_CC74_ADDRESS 0x{cc74_address:08X}UL",
        f"#define SRK_R23_PROOF_SCSP_CONTROL_OFFSET {SATURN_MIDI_68K_SCSP_SLOT_CONTROL * 2}UL",
        f"#define SRK_R23_PROOF_SCSP_PITCH_OFFSET {SATURN_MIDI_68K_SCSP_SLOT_PITCH * 2}UL",
        f"#define SRK_R23_PROOF_SCSP_MIXER_OFFSET {SATURN_MIDI_68K_SCSP_SLOT_MIXER * 2}UL",
        f"#define SRK_R23_PROOF_KYONB 0x{SATURN_MIDI_68K_SCSP_CONTROL_KYONB:04X}u",
        f"#define SRK_R23_PROOF_EXPECTED_ON_PITCH 0x{expected_on.pitch:04X}u",
        f"#define SRK_R23_PROOF_EXPECTED_ON_MIXER 0x{expected_on.mixer:04X}u",
        f"#define SRK_R23_PROOF_EXPECTED_OFF_PITCH 0x{expected_off.pitch:04X}u",
        f"#define SRK_R23_PROOF_EXPECTED_OFF_MIXER 0x{expected_off.mixer:04X}u",
        "",
    ]
    lines.extend(_render_events("srk_r23_proof_batch1", batches[0].records))
    lines.extend(_render_events("srk_r23_proof_batch2", batches[1].records))
    lines.extend(_render_words("srk_r23_expected_summary", summaries))
    lines.extend(_render_words("srk_r23_expected_controllers", controllers))
    lines.extend(_render_words("srk_r23_expected_active", active))
    lines.extend(_render_words("srk_r23_expected_voice_on", voice_on))
    lines.extend(_render_words("srk_r23_expected_voice_off", voice_off))
    lines.extend(
        (
            "static unsigned short srk_r23_read(unsigned long address)",
            "{",
            "    return SRK_R23_PROOF_RAM[address >> 1];",
            "}",
            "",
            "static void srk_r23_write(unsigned long address, unsigned short value)",
            "{",
            "    SRK_R23_PROOF_RAM[address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_r23_scsp(unsigned long offset)",
            "{",
            "    return SRK_R23_PROOF_SCSP[offset >> 1];",
            "}",
            "",
            "static unsigned short srk_r23_service(unsigned long offset)",
            "{",
            "    return srk_r23_read(SRK_R23_PROOF_SERVICE + offset);",
            "}",
            "",
            "static unsigned short srk_r23_mailbox(unsigned long word_index)",
            "{",
            "    return srk_r23_read(SRK_MIDI_MAILBOX_ADDRESS + (word_index * 2UL));",
            "}",
            "",
            "static unsigned short srk_r23_voice(unsigned short word_index)",
            "{",
            "    return srk_r23_read(SRK_R23_PROOF_VOICE_ADDRESS + ((unsigned long)word_index * 2UL));",
            "}",
            "",
            "static int srk_r23_install(void)",
            "{",
            "    unsigned long index;",
            "    for(index=0UL; index<0x0100UL; index+=2UL)",
            "        srk_r23_write(SRK_MIDI_MAILBOX_ADDRESS + index, 0u);",
            "    for(index=0UL; index<0x0200UL; index+=2UL)",
            "        srk_r23_write(SRK_R23_PROOF_SERVICE + index, 0u);",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++)",
            "        srk_r23_write(",
            "            SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_resident_audio_service_program[index]);",
            "    srk_r23_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS >> 16));",
            "    srk_r23_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_AUDIO_STACK_ADDRESS & 0xFFFFUL));",
            "    srk_r23_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS >> 16));",
            "    srk_r23_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS & 0xFFFFUL));",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_r23_read(SRK_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_resident_audio_service_program[index]) return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static void srk_r23_capture(SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short total_hi;",
            "    state->telemetry.flags = srk_r23_mailbox(SRK_MIDI_MB_FLAGS);",
            "    state->telemetry.read_sequence = srk_r23_mailbox(SRK_MIDI_MB_READ_SEQUENCE);",
            "    state->telemetry.read_index = srk_r23_mailbox(SRK_MIDI_MB_READ_INDEX);",
            "    state->telemetry.last_error = srk_r23_mailbox(SRK_MIDI_MB_LAST_ERROR);",
            "    state->telemetry.stream_flags = srk_r23_service(SRK_R23_PROOF_SERVICE_FLAGS_OFFSET);",
            "    state->telemetry.current_index = srk_r23_service(SRK_R23_PROOF_CURRENT_INDEX_OFFSET);",
            "    state->telemetry.batch_count = srk_r23_service(SRK_R23_PROOF_BATCH_COUNT_OFFSET);",
            "    total_hi = srk_r23_service(SRK_R23_PROOF_TOTAL_HI_OFFSET);",
            "    state->telemetry.total_processed = srk_r23_service(SRK_R23_PROOF_TOTAL_LO_OFFSET);",
            "    if(total_hi != 0u) state->telemetry.total_processed = 0xFFFFu;",
            f"    state->telemetry.voice_active = srk_r23_voice({SATURN_MIDI_68K_VOICE_ACTIVE_WORD}u);",
            f"    state->telemetry.voice_generation = srk_r23_voice({SATURN_MIDI_68K_VOICE_GENERATION_WORD}u);",
            f"    state->telemetry.voice_note = srk_r23_voice({SATURN_MIDI_68K_VOICE_NOTE_WORD}u);",
            f"    state->telemetry.voice_velocity = srk_r23_voice({SATURN_MIDI_68K_VOICE_VELOCITY_WORD}u);",
            f"    state->telemetry.voice_key_on_count = srk_r23_voice({SATURN_MIDI_68K_VOICE_KEY_ON_COUNT_WORD}u);",
            f"    state->telemetry.voice_key_off_count = srk_r23_voice({SATURN_MIDI_68K_VOICE_KEY_OFF_COUNT_WORD}u);",
            f"    state->telemetry.voice_last_error = srk_r23_voice({SATURN_MIDI_68K_VOICE_LAST_ERROR_WORD}u);",
            f"    state->telemetry.voice_pitch = srk_r23_voice({SATURN_MIDI_68K_VOICE_PITCH_WORD}u);",
            f"    state->telemetry.voice_mixer = srk_r23_voice({SATURN_MIDI_68K_VOICE_MIXER_WORD}u);",
            f"    state->telemetry.voice_control = srk_r23_voice({11}u);",
            "    state->telemetry.scsp_control = srk_r23_scsp(SRK_R23_PROOF_SCSP_CONTROL_OFFSET);",
            "    state->telemetry.scsp_pitch = srk_r23_scsp(SRK_R23_PROOF_SCSP_PITCH_OFFSET);",
            "    state->telemetry.scsp_mixer = srk_r23_scsp(SRK_R23_PROOF_SCSP_MIXER_OFFSET);",
            "    state->telemetry.final_cc74 = (unsigned short)(srk_r23_read(SRK_R23_PROOF_CC74_ADDRESS) >> 8);",
            "}",
            "",
            "static int srk_r23_verify_region(",
            "    unsigned long address, const unsigned short *expected, unsigned short count,",
            "    unsigned short region, SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short index;",
            "    unsigned short actual;",
            "    for(index=0u; index<count; index++){",
            "        actual = srk_r23_read(address + ((unsigned long)index * 2UL));",
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
            "static int srk_r23_verify_voice(",
            "    const unsigned short *expected, SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            f"    return srk_r23_verify_region(SRK_R23_PROOF_VOICE_ADDRESS, expected, {SATURN_MIDI_68K_VOICE_STATE_WORDS}u, {SATURN_MIDI_68K_R23_VERIFY_VOICE_MISMATCH}u, state);",
            "}",
            "",
            "static int srk_r23_verify_scsp_on(SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    if((state->telemetry.scsp_control & SRK_R23_PROOF_KYONB) == 0u ||",
            "       state->telemetry.scsp_pitch != SRK_R23_PROOF_EXPECTED_ON_PITCH ||",
            "       state->telemetry.scsp_mixer != SRK_R23_PROOF_EXPECTED_ON_MIXER){",
            f"        state->telemetry.state_verify_status = {SATURN_MIDI_68K_R23_VERIFY_SCSP_MISMATCH}u;",
            "        state->telemetry.mismatch_region = state->telemetry.state_verify_status;",
            "        state->telemetry.mismatch_index = 0u;",
            "        state->telemetry.expected_value = SRK_R23_PROOF_EXPECTED_ON_MIXER;",
            "        state->telemetry.actual_value = state->telemetry.scsp_mixer;",
            "        return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_r23_verify_scsp_off(SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    if((state->telemetry.scsp_control & SRK_R23_PROOF_KYONB) != 0u ||",
            "       state->telemetry.scsp_pitch != SRK_R23_PROOF_EXPECTED_OFF_PITCH ||",
            "       state->telemetry.scsp_mixer != SRK_R23_PROOF_EXPECTED_OFF_MIXER){",
            f"        state->telemetry.state_verify_status = {SATURN_MIDI_68K_R23_VERIFY_SCSP_MISMATCH}u;",
            "        state->telemetry.mismatch_region = state->telemetry.state_verify_status;",
            "        state->telemetry.mismatch_index = 1u;",
            "        state->telemetry.expected_value = SRK_R23_PROOF_EXPECTED_OFF_MIXER;",
            "        state->telemetry.actual_value = state->telemetry.scsp_mixer;",
            "        return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static int srk_r23_verify_final_midi_state(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            f"    if(!srk_r23_verify_region(SRK_R23_PROOF_SUMMARY_ADDRESS, srk_r23_expected_summary, {len(summaries)}u, {SATURN_MIDI_68K_R23_VERIFY_SUMMARY_MISMATCH}u, state)) return 0;",
            f"    if(!srk_r23_verify_region(SRK_R23_PROOF_CONTROLLER_ADDRESS, srk_r23_expected_controllers, {len(controllers)}u, {SATURN_MIDI_68K_R23_VERIFY_CONTROLLER_MISMATCH}u, state)) return 0;",
            f"    if(!srk_r23_verify_region(SRK_R23_PROOF_ACTIVE_ADDRESS, srk_r23_expected_active, {len(active)}u, {SATURN_MIDI_68K_R23_VERIFY_ACTIVE_NOTE_MISMATCH}u, state)) return 0;",
            "    return 1;",
            "}",
            "",
            "static unsigned int srk_r23_fail(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state, unsigned short code)",
            "{",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_ERROR}u;",
            "    if(state->telemetry.last_error == 0u) state->telemetry.last_error = code;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    return state->runtime_status;",
            "}",
            "",
            "void srk_saturn_midi_68k_r23_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
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
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_NOT_STARTED}u;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r23_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops;",
            "    if(!state) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted) return state->runtime_status;",
            "    state->attempted = 1u;",
            "    ops = srk_saturn_midi_68k_hardware_adapter_ops();",
            "    if(!ops || !ops->stop_sound_cpu || !ops->start_sound_cpu)",
            "        return srk_r23_fail(state, 0xE101u);",
            "    if(!ops->stop_sound_cpu()) return srk_r23_fail(state, 0xE102u);",
            "    if(!srk_r23_install()) return srk_r23_fail(state, 0xE103u);",
            "    if(!ops->start_sound_cpu()) return srk_r23_fail(state, 0xE104u);",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_RUNNING;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_BOOT}u;",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r23_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short phase;",
            "    if(!state || !state->attempted) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "    state->poll_count += 1u;",
            "    srk_r23_capture(state);",
            "    phase = state->telemetry.phase;",
            "    if((state->telemetry.stream_flags & SRK_R23_PROOF_ERROR) != 0u ||",
            "       srk_r23_service(SRK_R23_PROOF_LAST_ERROR_OFFSET) != 0u ||",
            "       state->telemetry.last_error != 0u || state->telemetry.voice_last_error != 0u)",
            "        return srk_r23_fail(state, 0xE110u);",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_BOOT}u){{",
            "        if(srk_r23_service(SRK_R23_PROOF_SERVICE_MAGIC_OFFSET) == SRK_R23_PROOF_SERVICE_MAGIC &&",
            "           srk_r23_service(SRK_R23_PROOF_SERVICE_VERSION_OFFSET) == SRK_R23_PROOF_SERVICE_VERSION &&",
            "           state->telemetry.stream_flags == SRK_R23_PROOF_WAIT_BATCH){",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_0_US}UL);",
            f"            if(!srk_saturn_midi_stream_batch_publish(srk_r23_proof_batch1, {SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS}u, 1u))",
            "                return srk_r23_fail(state, 0xE111u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_ZERO}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_ZERO}u){{",
            "        if(state->telemetry.stream_flags == SRK_R23_PROOF_WAIT_TIME &&",
            "           state->telemetry.current_index == 0u && state->telemetry.read_sequence == 0u &&",
            "           state->telemetry.total_processed == 0u){",
            "            state->telemetry.wait_zero_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_PARTIAL}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_PARTIAL}u){{",
            "        if(state->telemetry.current_index == 15u && state->telemetry.total_processed == 15u &&",
            "           state->telemetry.read_sequence == 0u){",
            "            state->telemetry.partial_15ms_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_BATCH1_ACK}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_BATCH1_ACK}u){{",
            "        if(state->telemetry.read_sequence == 1u && state->telemetry.read_index == 32u &&",
            "           state->telemetry.batch_count == 1u && state->telemetry.total_processed == 32u){",
            "            state->telemetry.batch1_ack_pass = 1u;",
            f"            if(!srk_saturn_midi_stream_batch_publish(srk_r23_proof_batch2, {SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS}u, 2u))",
            "                return srk_r23_fail(state, 0xE112u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_REFILL}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_REFILL}u){{",
            "        if(state->telemetry.stream_flags == SRK_R23_PROOF_WAIT_TIME &&",
            "           state->telemetry.current_index == 0u && state->telemetry.read_sequence == 1u &&",
            "           state->telemetry.total_processed == 32u && state->telemetry.voice_active == 0u){",
            "            state->telemetry.refill_wait_pass = 1u;",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_ON}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_ON}u){{",
            "        if(state->telemetry.current_index == 1u && state->telemetry.read_sequence == 1u &&",
            "           state->telemetry.total_processed == 33u){",
            "            if(!srk_r23_verify_voice(srk_r23_expected_voice_on, state))",
            "                return srk_r23_fail(state, 0xE113u);",
            "            srk_r23_capture(state);",
            "            if(!srk_r23_verify_scsp_on(state)) return srk_r23_fail(state, 0xE114u);",
            "            state->telemetry.key_on_pass = 1u;",
            "            state->telemetry.audible_hold_polls = 0u;",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_AUDIBLE_HOLD}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_AUDIBLE_HOLD}u){{",
            "        if(state->telemetry.current_index != 1u || state->telemetry.read_sequence != 1u ||",
            "           state->telemetry.total_processed != 33u || state->telemetry.voice_active != 1u)",
            "            return srk_r23_fail(state, 0xE115u);",
            "        if((state->telemetry.scsp_control & SRK_R23_PROOF_KYONB) == 0u)",
            "            return srk_r23_fail(state, 0xE116u);",
            "        state->telemetry.audible_hold_polls += 1u;",
            f"        if(state->telemetry.audible_hold_polls >= {SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS}u){{",
            f"            srk_saturn_midi_stream_clock_publish({SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US}UL);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_OFF}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_WAIT_KEY_OFF}u){{",
            "        if(state->telemetry.read_sequence == 2u && state->telemetry.read_index == 2u &&",
            "           state->telemetry.batch_count == 2u && state->telemetry.total_processed == 34u){",
            "            if(!srk_r23_verify_voice(srk_r23_expected_voice_off, state))",
            "                return srk_r23_fail(state, 0xE117u);",
            "            srk_r23_capture(state);",
            "            if(!srk_r23_verify_scsp_off(state)) return srk_r23_fail(state, 0xE118u);",
            "            state->telemetry.key_off_pass = 1u;",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_VERIFY_STATE}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(phase == {SATURN_MIDI_68K_R23_PHASE_VERIFY_STATE}u){{",
            "        if(!srk_r23_verify_final_midi_state(state))",
            "            return srk_r23_fail(state, 0xE119u);",
            "        srk_r23_capture(state);",
            f"        if(state->telemetry.final_cc74 != {snapshot.cc74}u ||",
            f"           srk_r23_read(SRK_R23_PROOF_ACTIVE_COUNT_ADDRESS) != {snapshot.final_active_note_count}u ||",
            f"           state->telemetry.voice_key_on_count != {snapshot.voice_key_on_count}u ||",
            f"           state->telemetry.voice_key_off_count != {snapshot.voice_key_off_count}u)",
            "            return srk_r23_fail(state, 0xE11Au);",
            f"        state->telemetry.state_verify_status = {SATURN_MIDI_68K_R23_VERIFY_PASS}u;",
            f"        state->telemetry.phase = {SATURN_MIDI_68K_R23_PHASE_PASS}u;",
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
_AUDIO_DEFINE = "#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1"
_STREAM_MENU_LABEL = '"MIDI 68K Stream Proof"'
_AUDIO_MENU_LABEL = '"MIDI 68K Audio Proof"'
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
_AUDIO_GUARD = (
    _STREAM_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE)"
)


def _stream_telemetry_block() -> str:
    return "\n".join(
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


def _audio_telemetry_block() -> str:
    return "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.phase);",
            '    srk_midi_68k_draw_field(2, 12, 12, "Phase:");',
            "    srk_midi_68k_draw_field(14, 12, 8, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.total_processed);",
            '    srk_midi_68k_draw_field(23, 12, 8, "Total:");',
            "    srk_midi_68k_draw_field(31, 12, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.wait_zero_pass);",
            '    srk_midi_68k_draw_field(2, 13, 14, "Wait @ 0us:");',
            "    srk_midi_68k_draw_field(16, 13, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.partial_15ms_pass);",
            '    srk_midi_68k_draw_field(22, 13, 10, "15ms=15:");',
            "    srk_midi_68k_draw_field(32, 13, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch1_ack_pass);",
            '    srk_midi_68k_draw_field(2, 14, 14, "Batch1 ACK:");',
            "    srk_midi_68k_draw_field(16, 14, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.refill_wait_pass);",
            '    srk_midi_68k_draw_field(22, 14, 10, "Refill:");',
            "    srk_midi_68k_draw_field(32, 14, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.key_on_pass);",
            '    srk_midi_68k_draw_field(2, 15, 14, "Key On:");',
            "    srk_midi_68k_draw_field(16, 15, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.audible_hold_polls);",
            '    srk_midi_68k_draw_field(22, 15, 10, "Hold:");',
            "    srk_midi_68k_draw_field(32, 15, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.key_off_pass);",
            '    srk_midi_68k_draw_field(2, 16, 14, "Key Off:");',
            "    srk_midi_68k_draw_field(16, 16, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify_status);",
            '    srk_midi_68k_draw_field(22, 16, 10, "State:");',
            "    srk_midi_68k_draw_field(32, 16, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_active);",
            '    srk_midi_68k_draw_field(2, 17, 14, "Voice active:");',
            "    srk_midi_68k_draw_field(16, 17, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_note);",
            '    srk_midi_68k_draw_field(22, 17, 10, "Note:");',
            "    srk_midi_68k_draw_field(32, 17, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_on_count);",
            '    srk_midi_68k_draw_field(2, 18, 14, "On count:");',
            "    srk_midi_68k_draw_field(16, 18, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_off_count);",
            '    srk_midi_68k_draw_field(22, 18, 10, "Off count:");',
            "    srk_midi_68k_draw_field(32, 18, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.scsp_control);",
            '    srk_midi_68k_draw_field(2, 19, 14, "SCSP ctl:");',
            "    srk_midi_68k_draw_field(16, 19, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.scsp_pitch);",
            '    srk_midi_68k_draw_field(2, 20, 14, "SCSP pitch:");',
            "    srk_midi_68k_draw_field(16, 20, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.scsp_mixer);",
            '    srk_midi_68k_draw_field(2, 21, 14, "SCSP mixer:");',
            "    srk_midi_68k_draw_field(16, 21, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.final_cc74);",
            '    srk_midi_68k_draw_field(2, 22, 14, "CC74:");',
            "    srk_midi_68k_draw_field(16, 22, 10, number);",
            "#endif",
        )
    )


def derive_resident_audio_candidate_main(stream_main: str) -> str:
    """Transform only a copied R22A stream-candidate main into the R23 proof."""

    if not stream_main.startswith(_STREAM_DEFINE + "\n"):
        raise RuntimeError("R22A main no longer begins with the accepted stream candidate define")
    main = _AUDIO_DEFINE + stream_main[len(_STREAM_DEFINE):]

    if main.count(_STREAM_GUARD) < 2:
        raise RuntimeError("R22A proof preprocessor guard shape changed")
    main = main.replace(_STREAM_GUARD, _AUDIO_GUARD)

    stream_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_stream_physical_proof.h"',
            "#endif",
        )
    )
    if main.count(stream_include) != 1:
        raise RuntimeError("R22A stream proof include block shape changed")
    main = main.replace(
        stream_include,
        "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE\n"
        '#include "srk_saturn_midi_68k_r23_physical_proof.h"\n'
        "#endif",
        1,
    )

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
    audio_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_R23_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K AUDIO PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "32+2 refill - MIDI drives SCSP slot 0"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Audio PASS: heard MIDI note + key off"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r23_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r23_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r23_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(stream_alias) != 1:
        raise RuntimeError("R22A stream proof alias block shape changed")
    main = main.replace(stream_alias, audio_alias, 1)

    stream_telemetry = _stream_telemetry_block()
    if main.count(stream_telemetry) != 1:
        raise RuntimeError("R22A stream telemetry rendering shape changed")
    main = main.replace(stream_telemetry, _audio_telemetry_block(), 1)

    stream_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(stream_success) != 1:
        raise RuntimeError("R22A success rendering shape changed")
    main = main.replace(
        stream_success,
        "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE\n"
        "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        1,
    )

    required = (
        _AUDIO_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
        '"MIDI / 68K AUDIO PROOF"',
        '"Audio PASS: heard MIDI note + key off"',
        "srk_saturn_midi_68k_r23_physical_proof_begin",
        "telemetry.key_on_pass",
        "telemetry.audible_hold_polls",
        "telemetry.key_off_pass",
        "telemetry.scsp_control",
    )
    for marker in required:
        if marker not in main:
            raise RuntimeError(f"derived R23 candidate main missing marker: {marker}")
    return main


def derive_resident_audio_candidate_menu(stream_menu: str) -> str:
    if stream_menu.count(_STREAM_MENU_LABEL) != 1:
        raise RuntimeError("R22A stream proof menu label is no longer isolated")
    menu = stream_menu.replace(_STREAM_MENU_LABEL, _AUDIO_MENU_LABEL, 1)
    if menu.count(_AUDIO_MENU_LABEL) != 1:
        raise RuntimeError("R23 audio proof menu label derivation failed")
    return menu
