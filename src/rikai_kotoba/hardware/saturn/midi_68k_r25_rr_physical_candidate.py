"""R25 RR physical-calibration proof renderer.

This layer binds one explicit calibration RR to the accepted Saturn-native R24
FRT clock and R25 calibration-only two-second release-ownership image.  The
physical program is deliberately tiny: one A4 Note On at 250 ms and one Note
Off at 1.25 s.  The SH-2 publishes monotonic FRT-derived microseconds while the
resident MC68EC000 owns the SCSP release tail for two further seconds.

SCSP does not expose envelope level/phase through the slot monitor, so this
proof never claims automatic silence detection.  It exposes deterministic
machine timing and release-ledger telemetry for operator/audio observation.
"""

from __future__ import annotations

from . import midi_68k_r24_physical_candidate as _r24
from .midi_68k_r25_release_lifecycle import SaturnMidi68KR25SlotPhase
from .midi_68k_r25_resident_audio_service import (
    SATURN_MIDI_68K_R25_SLOT_BASE_WORD,
    SATURN_MIDI_68K_R25_SLOT_PHASE_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD,
    SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD,
    SATURN_MIDI_68K_R25_SLOT_WORDS,
    SATURN_MIDI_68K_R25_VOICE_BUSY_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_EG1_WORD,
    SATURN_MIDI_68K_R25_VOICE_EG2_WORD,
    SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_KEY_OFF_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD,
    SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_RELEASE_COMPLETED_WORD,
    SATURN_MIDI_68K_R25_VOICE_RELEASE_STARTED_WORD,
    SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD,
    SATURN_MIDI_68K_R25_VOICE_RR_WORD,
    SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS,
)
from .midi_68k_r25_rr_physical_calibration import (
    SATURN_MIDI_68K_R25_CALIBRATION_END_US,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US,
    SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US,
    SATURN_MIDI_68K_R25_CALIBRATION_VELOCITY,
    build_saturn_midi_68k_r25_rr_calibration_program,
    build_saturn_midi_68k_r25_rr_physical_calibration_plan,
)
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
)


SATURN_MIDI_68K_R25_CAL_PHASE_NOT_STARTED = 0
SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_BOOT = 1
SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_ON = 2
SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_OFF = 3
SATURN_MIDI_68K_R25_CAL_PHASE_OBSERVE_RELEASE = 4
SATURN_MIDI_68K_R25_CAL_PHASE_PASS = 5
SATURN_MIDI_68K_R25_CAL_PHASE_ERROR = 6
SATURN_MIDI_68K_R25_CAL_TIMEOUT_US = SATURN_MIDI_68K_R25_CALIBRATION_END_US + 500_000

_R24_DEFINE = "#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1"
_R25_DEFINE = "#define SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE 1"
_R24_MENU_LABEL = '"MIDI 68K Song Proof"'
_R25_MENU_LABEL = '"MIDI 68K R25 RR Cal"'
_R25_GUARD = (
    _r24._R24_GUARD
    + " || "
    + chr(92)
    + "\n    defined(SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE)"
)


def _slot_word(slot: int, field: int) -> int:
    return SATURN_MIDI_68K_R25_SLOT_BASE_WORD + slot * SATURN_MIDI_68K_R25_SLOT_WORDS + field


def _render_events(release_rate: int) -> list[str]:
    plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    program = build_saturn_midi_68k_r25_rr_calibration_program()
    lines = ["static const SRK_SATURN_MIDI_EVENT srk_r25_cal_events[] = {"]
    for record in program.records:
        lines.append(
            "    {"
            f"{record.time_us}UL, {int(record.opcode)}u, {record.channel}u, "
            f"{record.data0}u, {record.data1}u"
            "},"
        )
    lines.extend(("};", ""))
    if plan.record_count != 2 or plan.batch_count != 1:
        raise RuntimeError("R25 RR physical calibration program shape changed")
    return lines


def render_srk_saturn_midi_68k_r25_rr_calibration_proof_header(*, release_rate: int) -> str:
    build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R25_RR_CALIBRATION_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_R25_RR_CALIBRATION_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_68k_r24_frt_backend.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R25_RR_CAL_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "    unsigned short phase;",
            "    unsigned short stream_flags;",
            "    unsigned short current_index;",
            "    unsigned short batch_count;",
            "    unsigned short total_processed;",
            "    unsigned short clock_pal;",
            "    unsigned short clock_group_b;",
            "    unsigned long clock_source_hz;",
            "    unsigned long clock_us;",
            "    unsigned long release_elapsed_us;",
            "    unsigned short release_rate;",
            "    unsigned short eg1;",
            "    unsigned short eg2;",
            "    unsigned short voice_key_on_count;",
            "    unsigned short voice_key_off_count;",
            "    unsigned short voice_busy_count;",
            "    unsigned short voice_held_count;",
            "    unsigned short voice_releasing_count;",
            "    unsigned short voice_owned_count;",
            "    unsigned short voice_release_started;",
            "    unsigned short voice_release_completed;",
            "    unsigned short voice_last_error;",
            "    unsigned short slot0_phase;",
            "    unsigned long slot0_release_start_us;",
            "    unsigned long slot0_release_deadline_us;",
            "} SRK_SATURN_MIDI_68K_R25_RR_CAL_TELEMETRY;",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_TELEMETRY telemetry;",
            "    SRK_MIDI_R24_FRT_CLOCK clock;",
            "    unsigned char original_tcr;",
            "    unsigned char frt_configured;",
            "} SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_r25_rr_calibration_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r25_rr_calibration_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r25_rr_calibration_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r25_rr_calibration_proof_source(*, release_rate: int) -> str:
    plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    releasing = int(SaturnMidi68KR25SlotPhase.RELEASING)
    held = int(SaturnMidi68KR25SlotPhase.HELD)
    free = int(SaturnMidi68KR25SlotPhase.FREE)
    lines = [
        '#include "srk_saturn_midi_68k_r25_rr_calibration_proof.h"',
        '#include "srk_saturn_midi_68k_hardware_adapter.h"',
        '#include "srk_saturn_midi_68k_installer.h"',
        '#include "srk_saturn_midi_68k_r25_resident_audio_service.h"',
        '#include "srk_saturn_midi_68k_r25_voice_state.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_R25_CAL_RAM ((volatile unsigned short *)0x25A00000UL)",
        f"#define SRK_R25_CAL_SERVICE 0x{SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS:08X}UL",
        f"#define SRK_R25_CAL_SERVICE_MAGIC_OFFSET {SATURN_MIDI_68K_STREAM_MAGIC_OFFSET}UL",
        f"#define SRK_R25_CAL_SERVICE_VERSION_OFFSET {SATURN_MIDI_68K_STREAM_VERSION_OFFSET}UL",
        f"#define SRK_R25_CAL_SERVICE_FLAGS_OFFSET {SATURN_MIDI_68K_STREAM_FLAGS_OFFSET}UL",
        f"#define SRK_R25_CAL_CURRENT_INDEX_OFFSET {SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET}UL",
        f"#define SRK_R25_CAL_BATCH_COUNT_OFFSET {SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET}UL",
        f"#define SRK_R25_CAL_TOTAL_HI_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET}UL",
        f"#define SRK_R25_CAL_TOTAL_LO_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET}UL",
        f"#define SRK_R25_CAL_LAST_ERROR_OFFSET {SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET}UL",
        f"#define SRK_R25_CAL_SERVICE_MAGIC 0x{SATURN_MIDI_68K_STREAM_SERVICE_MAGIC:04X}u",
        f"#define SRK_R25_CAL_SERVICE_VERSION {SATURN_MIDI_68K_STREAM_SERVICE_VERSION}u",
        f"#define SRK_R25_CAL_WAIT_BATCH 0x{SATURN_MIDI_68K_STREAM_FLAG_WAIT_BATCH:04X}u",
        f"#define SRK_R25_CAL_STREAM_ERROR 0x{SATURN_MIDI_68K_STREAM_FLAG_ERROR:04X}u",
        f"#define SRK_R25_CAL_VOICE_ADDRESS 0x{SATURN_MIDI_68K_R25_VOICE_STATE_ADDRESS:08X}UL",
        f"#define SRK_R25_CAL_TVMD (*(volatile unsigned short *)0x{_r24.SATURN_MIDI_68K_R24_VDP2_TVMD_ADDRESS:08X}UL)",
        f"#define SRK_R25_CAL_TVSTAT (*(volatile unsigned short *)0x{_r24.SATURN_MIDI_68K_R24_VDP2_TVSTAT_ADDRESS:08X}UL)",
        f"#define SRK_R25_CAL_FRT_TCR (*(volatile unsigned char *)0x{_r24.SATURN_MIDI_68K_R24_FRT_TCR_ADDRESS:08X}UL)",
        f"#define SRK_R25_CAL_CLOCK_NTSC_A {_r24.SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ}UL",
        f"#define SRK_R25_CAL_CLOCK_NTSC_B {_r24.SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ}UL",
        f"#define SRK_R25_CAL_CLOCK_PAL_A {_r24.SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ}UL",
        f"#define SRK_R25_CAL_CLOCK_PAL_B {_r24.SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ}UL",
        f"#define SRK_R25_CAL_NOTE_ON_US {SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US}UL",
        f"#define SRK_R25_CAL_NOTE_OFF_US {SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US}UL",
        f"#define SRK_R25_CAL_OBSERVATION_US {SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US}UL",
        f"#define SRK_R25_CAL_END_US {SATURN_MIDI_68K_R25_CALIBRATION_END_US}UL",
        f"#define SRK_R25_CAL_TIMEOUT_US {SATURN_MIDI_68K_R25_CAL_TIMEOUT_US}UL",
        f"#define SRK_R25_CAL_RELEASE_RATE {release_rate}u",
        f"#define SRK_R25_CAL_EXPECTED_EG1 0x{plan.eg1_word:04X}u",
        f"#define SRK_R25_CAL_EXPECTED_EG2 0x{plan.eg2_word:04X}u",
        f"#define SRK_R25_CAL_PHASE_HELD {held}u",
        f"#define SRK_R25_CAL_PHASE_RELEASING {releasing}u",
        f"#define SRK_R25_CAL_PHASE_FREE {free}u",
        "",
    ]
    lines.extend(_render_events(release_rate))
    lines.extend(
        (
            "static unsigned short srk_r25_cal_read(unsigned long address)",
            "{",
            "    return SRK_R25_CAL_RAM[address >> 1];",
            "}",
            "",
            "static void srk_r25_cal_write(unsigned long address, unsigned short value)",
            "{",
            "    SRK_R25_CAL_RAM[address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_r25_cal_service(unsigned long offset)",
            "{",
            "    return srk_r25_cal_read(SRK_R25_CAL_SERVICE + offset);",
            "}",
            "",
            "static unsigned short srk_r25_cal_mailbox(unsigned long word_index)",
            "{",
            "    return srk_r25_cal_read(SRK_MIDI_MAILBOX_ADDRESS + (word_index * 2UL));",
            "}",
            "",
            "static unsigned short srk_r25_cal_voice(unsigned short word_index)",
            "{",
            "    return srk_r25_cal_read(SRK_R25_CAL_VOICE_ADDRESS + ((unsigned long)word_index * 2UL));",
            "}",
            "",
            "static unsigned long srk_r25_cal_join(unsigned short high, unsigned short low)",
            "{",
            "    return ((unsigned long)high << 16) | (unsigned long)low;",
            "}",
            "",
            "static unsigned long srk_r25_cal_select_clock(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    unsigned short tvstat;",
            "    unsigned short tvmd;",
            "    tvstat = SRK_R25_CAL_TVSTAT;",
            "    tvmd = SRK_R25_CAL_TVMD;",
            "    state->telemetry.clock_pal = (unsigned short)(tvstat & 0x0001u);",
            "    state->telemetry.clock_group_b = (unsigned short)(tvmd & 0x0001u);",
            "    if(state->telemetry.clock_pal){",
            "        if(state->telemetry.clock_group_b) return SRK_R25_CAL_CLOCK_PAL_B;",
            "        return SRK_R25_CAL_CLOCK_PAL_A;",
            "    }",
            "    if(state->telemetry.clock_group_b) return SRK_R25_CAL_CLOCK_NTSC_B;",
            "    return SRK_R25_CAL_CLOCK_NTSC_A;",
            "}",
            "",
            "static int srk_r25_cal_install(void)",
            "{",
            "    unsigned long index;",
            "    for(index=0UL; index<0x0100UL; index+=2UL)",
            "        srk_r25_cal_write(SRK_MIDI_MAILBOX_ADDRESS + index, 0u);",
            "    for(index=0UL; index<0x0200UL; index+=2UL)",
            "        srk_r25_cal_write(SRK_R25_CAL_SERVICE + index, 0u);",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++)",
            "        srk_r25_cal_write(",
            "            SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_r25_resident_audio_service_program[index]);",
            "    srk_r25_cal_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_R25_RESIDENT_AUDIO_STACK_ADDRESS >> 16));",
            "    srk_r25_cal_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_R25_RESIDENT_AUDIO_STACK_ADDRESS & 0xFFFFUL));",
            "    srk_r25_cal_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS >> 16));",
            "    srk_r25_cal_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS & 0xFFFFUL));",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_r25_cal_read(SRK_MIDI_68K_R25_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_r25_resident_audio_service_program[index]) return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static void srk_r25_cal_capture(SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    unsigned short total_hi;",
            "    unsigned short start_hi;",
            "    unsigned short start_lo;",
            "    unsigned short deadline_hi;",
            "    unsigned short deadline_lo;",
            "    state->telemetry.flags = srk_r25_cal_mailbox(SRK_MIDI_MB_FLAGS);",
            "    state->telemetry.read_sequence = srk_r25_cal_mailbox(SRK_MIDI_MB_READ_SEQUENCE);",
            "    state->telemetry.read_index = srk_r25_cal_mailbox(SRK_MIDI_MB_READ_INDEX);",
            "    state->telemetry.last_error = srk_r25_cal_mailbox(SRK_MIDI_MB_LAST_ERROR);",
            "    state->telemetry.stream_flags = srk_r25_cal_service(SRK_R25_CAL_SERVICE_FLAGS_OFFSET);",
            "    state->telemetry.current_index = srk_r25_cal_service(SRK_R25_CAL_CURRENT_INDEX_OFFSET);",
            "    state->telemetry.batch_count = srk_r25_cal_service(SRK_R25_CAL_BATCH_COUNT_OFFSET);",
            "    total_hi = srk_r25_cal_service(SRK_R25_CAL_TOTAL_HI_OFFSET);",
            "    state->telemetry.total_processed = srk_r25_cal_service(SRK_R25_CAL_TOTAL_LO_OFFSET);",
            "    if(total_hi != 0u) state->telemetry.total_processed = 0xFFFFu;",
            f"    state->telemetry.voice_key_on_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_KEY_ON_COUNT_WORD}u);",
            f"    state->telemetry.voice_key_off_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_KEY_OFF_COUNT_WORD}u);",
            f"    state->telemetry.voice_busy_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_BUSY_COUNT_WORD}u);",
            f"    state->telemetry.voice_held_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_HELD_COUNT_WORD}u);",
            f"    state->telemetry.voice_releasing_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_RELEASING_COUNT_WORD}u);",
            f"    state->telemetry.voice_owned_count = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_OWNED_COUNT_WORD}u);",
            f"    state->telemetry.voice_release_started = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_RELEASE_STARTED_WORD}u);",
            f"    state->telemetry.voice_release_completed = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_RELEASE_COMPLETED_WORD}u);",
            f"    state->telemetry.voice_last_error = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_LAST_ERROR_WORD}u);",
            f"    state->telemetry.release_rate = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_RR_WORD}u);",
            f"    state->telemetry.eg1 = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_EG1_WORD}u);",
            f"    state->telemetry.eg2 = srk_r25_cal_voice({SATURN_MIDI_68K_R25_VOICE_EG2_WORD}u);",
            f"    state->telemetry.slot0_phase = srk_r25_cal_voice({_slot_word(0, SATURN_MIDI_68K_R25_SLOT_PHASE_WORD)}u);",
            f"    start_hi = srk_r25_cal_voice({_slot_word(0, SATURN_MIDI_68K_R25_SLOT_RELEASE_START_HI_WORD)}u);",
            f"    start_lo = srk_r25_cal_voice({_slot_word(0, SATURN_MIDI_68K_R25_SLOT_RELEASE_START_LO_WORD)}u);",
            f"    deadline_hi = srk_r25_cal_voice({_slot_word(0, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_HI_WORD)}u);",
            f"    deadline_lo = srk_r25_cal_voice({_slot_word(0, SATURN_MIDI_68K_R25_SLOT_RELEASE_DEADLINE_LO_WORD)}u);",
            "    state->telemetry.slot0_release_start_us = srk_r25_cal_join(start_hi, start_lo);",
            "    state->telemetry.slot0_release_deadline_us = srk_r25_cal_join(deadline_hi, deadline_lo);",
            "    if(state->telemetry.clock_us >= SRK_R25_CAL_NOTE_OFF_US)",
            "        state->telemetry.release_elapsed_us = state->telemetry.clock_us - SRK_R25_CAL_NOTE_OFF_US;",
            "    else",
            "        state->telemetry.release_elapsed_us = 0UL;",
            "}",
            "",
            "static void srk_r25_cal_restore_frt(SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    if(state->frt_configured){",
            "        SRK_R25_CAL_FRT_TCR = state->original_tcr;",
            "        state->frt_configured = 0u;",
            "    }",
            "}",
            "",
            "static unsigned int srk_r25_cal_fail(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state, unsigned short code)",
            "{",
            "    srk_r25_cal_restore_frt(state);",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_ERROR}u;",
            "    if(state->telemetry.last_error == 0u) state->telemetry.last_error = code;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    return state->runtime_status;",
            "}",
            "",
            "void srk_saturn_midi_68k_r25_rr_calibration_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    unsigned char *bytes;",
            "    unsigned long count;",
            "    if(!state) return;",
            "    bytes = (unsigned char *)state;",
            "    count = (unsigned long)sizeof(*state);",
            "    while(count) bytes[--count] = 0u;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_NOT_STARTED}u;",
            "    srk_saturn_midi_r24_frt_reset(&state->clock);",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r25_rr_calibration_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops;",
            "    if(!state) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted) return state->runtime_status;",
            "    state->attempted = 1u;",
            "    ops = srk_saturn_midi_68k_hardware_adapter_ops();",
            "    if(!ops || !ops->stop_sound_cpu || !ops->start_sound_cpu)",
            "        return srk_r25_cal_fail(state, 0xE301u);",
            "    if(!ops->stop_sound_cpu()) return srk_r25_cal_fail(state, 0xE302u);",
            "    if(!srk_r25_cal_install()) return srk_r25_cal_fail(state, 0xE303u);",
            "    if(!ops->start_sound_cpu()) return srk_r25_cal_fail(state, 0xE304u);",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_RUNNING;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_BOOT}u;",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r25_rr_calibration_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE *state)",
            "{",
            "    unsigned long now_us;",
            "    if(!state || !state->attempted) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "    state->poll_count += 1u;",
            "    srk_r25_cal_capture(state);",
            "    if((state->telemetry.stream_flags & SRK_R25_CAL_STREAM_ERROR) != 0u ||",
            "       srk_r25_cal_service(SRK_R25_CAL_LAST_ERROR_OFFSET) != 0u ||",
            "       state->telemetry.last_error != 0u || state->telemetry.voice_last_error != 0u)",
            "        return srk_r25_cal_fail(state, 0xE310u);",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_BOOT}u){{",
            "        if(srk_r25_cal_service(SRK_R25_CAL_SERVICE_MAGIC_OFFSET) == SRK_R25_CAL_SERVICE_MAGIC &&",
            "           srk_r25_cal_service(SRK_R25_CAL_SERVICE_VERSION_OFFSET) == SRK_R25_CAL_SERVICE_VERSION &&",
            "           state->telemetry.stream_flags == SRK_R25_CAL_WAIT_BATCH){",
            "            state->telemetry.clock_source_hz = srk_r25_cal_select_clock(state);",
            "            state->original_tcr = SRK_R25_CAL_FRT_TCR;",
            "            state->frt_configured = 1u;",
            "            srk_saturn_midi_r24_frt_configure_div128();",
            "            srk_saturn_midi_r24_frt_reset(&state->clock);",
            "            now_us = srk_saturn_midi_r24_frt_sample_us(&state->clock, state->telemetry.clock_source_hz);",
            "            state->telemetry.clock_us = now_us;",
            "            srk_saturn_midi_stream_clock_publish(now_us);",
            "            if(!srk_saturn_midi_stream_batch_publish(srk_r25_cal_events, 2u, 1u))",
            "                return srk_r25_cal_fail(state, 0xE311u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_ON}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            "    now_us = srk_saturn_midi_r24_frt_sample_us(&state->clock, state->telemetry.clock_source_hz);",
            "    state->telemetry.clock_us = now_us;",
            "    srk_saturn_midi_stream_clock_publish(now_us);",
            "    srk_r25_cal_capture(state);",
            "    if((state->telemetry.stream_flags & SRK_R25_CAL_STREAM_ERROR) != 0u ||",
            "       srk_r25_cal_service(SRK_R25_CAL_LAST_ERROR_OFFSET) != 0u ||",
            "       state->telemetry.last_error != 0u || state->telemetry.voice_last_error != 0u)",
            "        return srk_r25_cal_fail(state, 0xE312u);",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_ON}u){{",
            "        if(state->telemetry.total_processed >= 1u){",
            "            if(state->telemetry.voice_key_on_count != 1u ||",
            "               state->telemetry.voice_held_count != 1u ||",
            "               state->telemetry.voice_releasing_count != 0u ||",
            "               state->telemetry.voice_owned_count != 1u ||",
            "               state->telemetry.voice_busy_count != 0u ||",
            "               state->telemetry.release_rate != SRK_R25_CAL_RELEASE_RATE ||",
            "               state->telemetry.eg1 != SRK_R25_CAL_EXPECTED_EG1 ||",
            "               state->telemetry.eg2 != SRK_R25_CAL_EXPECTED_EG2 ||",
            "               state->telemetry.slot0_phase != SRK_R25_CAL_PHASE_HELD)",
            "                return srk_r25_cal_fail(state, 0xE313u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_OFF}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R25_CAL_PHASE_WAIT_NOTE_OFF}u){{",
            "        if(state->telemetry.total_processed >= 2u){",
            "            if(state->telemetry.read_sequence != 1u || state->telemetry.read_index != 2u ||",
            "               state->telemetry.batch_count != 1u || state->telemetry.voice_key_off_count != 1u ||",
            "               state->telemetry.voice_held_count != 0u ||",
            "               state->telemetry.voice_releasing_count != 1u ||",
            "               state->telemetry.voice_owned_count != 1u ||",
            "               state->telemetry.voice_release_started != 1u ||",
            "               state->telemetry.slot0_phase != SRK_R25_CAL_PHASE_RELEASING ||",
            "               state->telemetry.slot0_release_start_us != SRK_R25_CAL_NOTE_OFF_US ||",
            "               state->telemetry.slot0_release_deadline_us != SRK_R25_CAL_END_US)",
            "                return srk_r25_cal_fail(state, 0xE314u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_OBSERVE_RELEASE}u;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R25_CAL_PHASE_OBSERVE_RELEASE}u){{",
            "        if(now_us < SRK_R25_CAL_END_US){",
            "            if(state->telemetry.voice_releasing_count != 1u ||",
            "               state->telemetry.voice_owned_count != 1u ||",
            "               state->telemetry.voice_release_completed != 0u ||",
            "               state->telemetry.slot0_phase != SRK_R25_CAL_PHASE_RELEASING)",
            "                return srk_r25_cal_fail(state, 0xE315u);",
            "            return state->runtime_status;",
            "        }",
            "        if(state->telemetry.voice_release_completed == 1u &&",
            "           state->telemetry.voice_releasing_count == 0u &&",
            "           state->telemetry.voice_owned_count == 0u &&",
            "           state->telemetry.slot0_phase == SRK_R25_CAL_PHASE_FREE){",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R25_CAL_PHASE_PASS}u;",
            "            srk_r25_cal_restore_frt(state);",
            "            state->runtime_status = SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;",
            "            return state->runtime_status;",
            "        }",
            "        if(now_us > SRK_R25_CAL_TIMEOUT_US)",
            "            return srk_r25_cal_fail(state, 0xE316u);",
            "        return state->runtime_status;",
            "    }",
            "",
            "    return state->runtime_status;",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def _r25_cal_telemetry_block(release_rate: int) -> str:
    return "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.phase);",
            '    srk_midi_68k_draw_field(2, 12, 7, "Phase:");',
            "    srk_midi_68k_draw_field(9, 12, 4, number);",
            f'    srk_midi_68k_draw_field(15, 12, 6, "RR {release_rate:02d}");',
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_us);",
            '    srk_midi_68k_draw_field(23, 12, 7, "Clock:");',
            "    srk_midi_68k_draw_field(30, 12, 10, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.release_elapsed_us);",
            '    srk_midi_68k_draw_field(2, 13, 12, "Since off:");',
            "    srk_midi_68k_draw_field(14, 13, 10, number);",
            '    srk_midi_68k_draw_field(25, 13, 15, "us / 2000000");',
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.total_processed);",
            '    srk_midi_68k_draw_field(2, 14, 9, "Records:");',
            "    srk_midi_68k_draw_field(11, 14, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_sequence);",
            '    srk_midi_68k_draw_field(16, 14, 5, "Seq:");',
            "    srk_midi_68k_draw_field(21, 14, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_index);",
            '    srk_midi_68k_draw_field(26, 14, 5, "Idx:");',
            "    srk_midi_68k_draw_field(31, 14, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_on_count);",
            '    srk_midi_68k_draw_field(2, 15, 8, "On:");',
            "    srk_midi_68k_draw_field(6, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_off_count);",
            '    srk_midi_68k_draw_field(11, 15, 8, "Off:");',
            "    srk_midi_68k_draw_field(16, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_busy_count);",
            '    srk_midi_68k_draw_field(21, 15, 8, "Busy:");',
            "    srk_midi_68k_draw_field(27, 15, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_held_count);",
            '    srk_midi_68k_draw_field(2, 16, 8, "Held:");',
            "    srk_midi_68k_draw_field(8, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_releasing_count);",
            '    srk_midi_68k_draw_field(13, 16, 8, "Rel:");',
            "    srk_midi_68k_draw_field(18, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_owned_count);",
            '    srk_midi_68k_draw_field(23, 16, 8, "Own:");',
            "    srk_midi_68k_draw_field(28, 16, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_release_started);",
            '    srk_midi_68k_draw_field(2, 17, 10, "Rel start:");',
            "    srk_midi_68k_draw_field(12, 17, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_release_completed);",
            '    srk_midi_68k_draw_field(17, 17, 10, "Rel done:");',
            "    srk_midi_68k_draw_field(27, 17, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.slot0_phase);",
            '    srk_midi_68k_draw_field(2, 18, 10, "Slot phase:");',
            "    srk_midi_68k_draw_field(12, 18, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.slot0_release_start_us);",
            '    srk_midi_68k_draw_field(17, 18, 7, "Start:");',
            "    srk_midi_68k_draw_field(24, 18, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.slot0_release_deadline_us);",
            '    srk_midi_68k_draw_field(2, 19, 10, "Deadline:");',
            "    srk_midi_68k_draw_field(12, 19, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_source_hz);",
            '    srk_midi_68k_draw_field(2, 20, 6, "Hz:");',
            "    srk_midi_68k_draw_field(6, 20, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_pal);",
            '    srk_midi_68k_draw_field(20, 20, 5, "PAL:");',
            "    srk_midi_68k_draw_field(25, 20, 2, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_group_b);",
            '    srk_midi_68k_draw_field(29, 20, 6, "GrpB:");',
            "    srk_midi_68k_draw_field(35, 20, 2, number);",
            "#endif",
        )
    )


def derive_r25_rr_calibration_candidate_main(r24_main: str, *, release_rate: int) -> str:
    plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    if not r24_main.startswith(_R24_DEFINE + "\n"):
        raise RuntimeError("R24 main no longer begins with the accepted candidate define")
    main = _R25_DEFINE + r24_main[len(_R24_DEFINE):]

    if main.count(_r24._R24_GUARD) < 2:
        raise RuntimeError("R24 proof preprocessor guard shape changed")
    main = main.replace(_r24._R24_GUARD, _R25_GUARD)

    r24_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_r24_physical_proof.h"',
            "#endif",
        )
    )
    r25_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE",
            '#include "srk_saturn_midi_68k_r25_rr_calibration_proof.h"',
            "#endif",
        )
    )
    if main.count(r24_include) != 1:
        raise RuntimeError("R24 proof include block shape changed")
    main = main.replace(r24_include, r25_include, 1)

    r24_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K REAL SONG"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "310 events - FRT clock - two SCSP voices"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Song PASS: 310 events / peak voices 2"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r24_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r24_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r24_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    r25_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_R25_RR_CAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K R25 RR CAL"',
            f'#define SRK_MIDI_68K_PROOF_SUBTITLE "RR {release_rate:02d} A4 - off 1.25s - observe 2.00s"',
            f'#define SRK_MIDI_68K_PROOF_SUCCESS "RR {release_rate:02d} probe done - production RR UNSET"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r25_rr_calibration_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r25_rr_calibration_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r25_rr_calibration_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(r24_alias) != 1:
        raise RuntimeError("R24 proof alias block shape changed")
    main = main.replace(r24_alias, r25_alias, 1)

    r24_telemetry = _r24._r24_telemetry_block()
    if main.count(r24_telemetry) != 1:
        raise RuntimeError("R24 telemetry block shape changed")
    main = main.replace(r24_telemetry, _r25_cal_telemetry_block(release_rate), 1)

    r24_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    r25_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(r24_success) != 1:
        raise RuntimeError("R24 success rendering shape changed")
    main = main.replace(r24_success, r25_success, 1)

    required = (
        _R25_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
        '"MIDI / 68K R25 RR CAL"',
        f'"RR {release_rate:02d} A4 - off 1.25s - observe 2.00s"',
        "srk_saturn_midi_68k_r25_rr_calibration_proof_begin",
        "telemetry.release_elapsed_us",
        "telemetry.voice_releasing_count",
        "telemetry.slot0_release_deadline_us",
    )
    for marker in required:
        if marker not in main:
            raise RuntimeError(f"derived R25 RR calibration main missing marker: {marker}")
    if plan.production_rr_selected:
        raise RuntimeError("R25 calibration derivation selected a production RR")
    return main


def derive_r25_rr_calibration_candidate_menu(r24_menu: str) -> str:
    if r24_menu.count(_R24_MENU_LABEL) != 1:
        raise RuntimeError("R24 song proof menu label is no longer isolated")
    menu = r24_menu.replace(_R24_MENU_LABEL, _R25_MENU_LABEL, 1)
    if menu.count(_R25_MENU_LABEL) != 1:
        raise RuntimeError("R25 RR calibration menu derivation failed")
    return menu
