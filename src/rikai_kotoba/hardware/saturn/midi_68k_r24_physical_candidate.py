"""R24 real-SMF physical proof for MIDI -> MC68EC000 -> two SCSP voices.

R23 is the immutable physical first-audio baseline.  R24 keeps its proven
resident queue/timestamp machinery but replaces the synthetic SH-2 clock with a
Saturn SH-2 FRT clock selected from the *runtime* VDP2 TV system and horizontal
clock group.  The proof drives the complete 310-record CC0 reference MIDI,
observes ten producer refills, verifies the final complete MIDI state and the
resident two-slot voice ledger, and restores the original FRT TCR on every
terminal path.

Clock selection follows Sega's documented SH-2 frequencies:

* NTSC graphic A (320/640): 26.8741 MHz
* NTSC graphic B (352/704): 28.6364 MHz
* PAL  graphic A (320/640): 26.6877 MHz
* PAL  graphic B (352/704): 28.4377 MHz

TVSTAT bit 0 supplies PAL/NTSC and TVMD HRESO bit 0 supplies A/B.  No region or
clock group is guessed by the host generator.
"""

from __future__ import annotations

from .midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_STATE_ADDRESS,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
)
from .midi_68k_r24_resident_audio_service import (
    SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD,
    SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD,
    SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD,
    SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD,
    SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD,
    SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD,
    SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS,
)
from .midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
    SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
    SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
    SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
    SaturnMidi68KR24SongProfile,
)
from .midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET,
    SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET,
    SATURN_MIDI_68K_STREAM_FLAG_ERROR,
    SATURN_MIDI_68K_STREAM_FLAGS_OFFSET,
    SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET,
    SATURN_MIDI_68K_STREAM_MAGIC_OFFSET,
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_MAGIC,
    SATURN_MIDI_68K_STREAM_SERVICE_VERSION,
    SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET,
    SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET,
    SATURN_MIDI_68K_STREAM_VERSION_OFFSET,
    simulate_srk_saturn_midi_stream_timeline,
)


SATURN_MIDI_68K_R24_PHASE_NOT_STARTED = 0
SATURN_MIDI_68K_R24_PHASE_WAIT_BOOT = 1
SATURN_MIDI_68K_R24_PHASE_PLAYING = 2
SATURN_MIDI_68K_R24_PHASE_VERIFY_STATE = 3
SATURN_MIDI_68K_R24_PHASE_PASS = 4
SATURN_MIDI_68K_R24_PHASE_ERROR = 5

SATURN_MIDI_68K_R24_VERIFY_NOT_RUN = 0
SATURN_MIDI_68K_R24_VERIFY_PASS = 1
SATURN_MIDI_68K_R24_VERIFY_SUMMARY_MISMATCH = 2
SATURN_MIDI_68K_R24_VERIFY_CONTROLLER_MISMATCH = 3
SATURN_MIDI_68K_R24_VERIFY_ACTIVE_NOTE_MISMATCH = 4
SATURN_MIDI_68K_R24_VERIFY_FINAL_CONTRACT_MISMATCH = 5

SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ = 26_874_100
SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ = 28_636_400
SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ = 26_687_700
SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ = 28_437_700
SATURN_MIDI_68K_R24_VDP2_TVMD_ADDRESS = 0x25F80000
SATURN_MIDI_68K_R24_VDP2_TVSTAT_ADDRESS = 0x25F80004
SATURN_MIDI_68K_R24_FRT_TCR_ADDRESS = 0xFFFFFE16
SATURN_MIDI_68K_R24_TIMEOUT_MARGIN_US = 5_000_000


def select_saturn_midi_68k_r24_source_hz(*, pal: bool, group_b: bool) -> int:
    if pal:
        return (
            SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ
            if group_b
            else SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ
        )
    return (
        SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ
        if group_b
        else SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ
    )


def _bytes_to_words(payload: bytes) -> tuple[int, ...]:
    if len(payload) & 1:
        raise RuntimeError("R24 physical proof payload is not word aligned")
    return tuple(
        (payload[index] << 8) | payload[index + 1]
        for index in range(0, len(payload), 2)
    )


def build_srk_saturn_midi_68k_r24_expected_midi_words(
    profile: SaturnMidi68KR24SongProfile,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    final = simulate_srk_saturn_midi_stream_timeline(
        profile.program,
        (profile.duration_us,),
    )[-1]
    return (
        pack_srk_saturn_midi_68k_state_words(final),
        _bytes_to_words(pack_srk_saturn_midi_68k_controller_bytes(final)),
        _bytes_to_words(pack_srk_saturn_midi_68k_active_note_bitmap(final)),
    )


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


def render_srk_saturn_midi_68k_r24_physical_proof_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            '#include "srk_saturn_midi_68k_r24_player.h"',
            '#include "srk_saturn_midi_68k_r24_frt_backend.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R24_PHYSICAL_TELEMETRY {",
            "    unsigned short flags;",
            "    unsigned short read_sequence;",
            "    unsigned short read_index;",
            "    unsigned short last_error;",
            "    unsigned short phase;",
            "    unsigned short stream_flags;",
            "    unsigned short current_index;",
            "    unsigned short batch_count;",
            "    unsigned short total_processed;",
            "    unsigned short player_sequence;",
            "    unsigned short player_batch_index;",
            "    unsigned short player_complete;",
            "    unsigned short player_error;",
            "    unsigned short clock_pal;",
            "    unsigned short clock_group_b;",
            "    unsigned long clock_source_hz;",
            "    unsigned long clock_us;",
            "    unsigned short voice_key_on_count;",
            "    unsigned short voice_key_off_count;",
            "    unsigned short voice_busy_count;",
            "    unsigned short voice_active_count;",
            "    unsigned short voice_peak_active;",
            "    unsigned short voice_last_error;",
            "    unsigned short polyphony_seen;",
            "    unsigned short state_verify_status;",
            "    unsigned short mismatch_region;",
            "    unsigned short mismatch_index;",
            "    unsigned short expected_value;",
            "    unsigned short actual_value;",
            "} SRK_SATURN_MIDI_68K_R24_PHYSICAL_TELEMETRY;",
            "",
            "typedef struct SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_TELEMETRY telemetry;",
            "    SRK_MIDI_R24_PLAYER_STATE player;",
            "    SRK_MIDI_R24_FRT_CLOCK clock;",
            "    unsigned short overlap_latched;",
            "    unsigned char original_tcr;",
            "    unsigned char frt_configured;",
            "} SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_r24_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r24_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state);",
            "unsigned int srk_saturn_midi_68k_r24_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state);",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_r24_physical_proof_source(
    profile: SaturnMidi68KR24SongProfile,
) -> str:
    if profile.record_count != SATURN_MIDI_68K_R24_REFERENCE_RECORDS:
        raise RuntimeError("R24 physical proof source is not the reviewed 310-record song")
    if len(profile.batches) != SATURN_MIDI_68K_R24_REFERENCE_BATCHES:
        raise RuntimeError("R24 physical proof source is not the reviewed ten-batch song")

    summaries, controllers, active = build_srk_saturn_midi_68k_r24_expected_midi_words(profile)
    duration = profile.duration_us
    timeout = duration + SATURN_MIDI_68K_R24_TIMEOUT_MARGIN_US

    lines = [
        '#include "srk_saturn_midi_68k_r24_physical_proof.h"',
        '#include "srk_saturn_midi_68k_hardware_adapter.h"',
        '#include "srk_saturn_midi_68k_installer.h"',
        '#include "srk_saturn_midi_68k_r24_resident_audio_service.h"',
        '#include "srk_saturn_midi_68k_r24_voice_state.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        '#include "srk_saturn_midi_mailbox.h"',
        "",
        "#define SRK_R24_PROOF_RAM ((volatile unsigned short *)0x25A00000UL)",
        f"#define SRK_R24_PROOF_SERVICE 0x{SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS:08X}UL",
        f"#define SRK_R24_PROOF_SERVICE_MAGIC_OFFSET {SATURN_MIDI_68K_STREAM_MAGIC_OFFSET}UL",
        f"#define SRK_R24_PROOF_SERVICE_VERSION_OFFSET {SATURN_MIDI_68K_STREAM_VERSION_OFFSET}UL",
        f"#define SRK_R24_PROOF_SERVICE_FLAGS_OFFSET {SATURN_MIDI_68K_STREAM_FLAGS_OFFSET}UL",
        f"#define SRK_R24_PROOF_CURRENT_INDEX_OFFSET {SATURN_MIDI_68K_STREAM_CURRENT_INDEX_OFFSET}UL",
        f"#define SRK_R24_PROOF_BATCH_COUNT_OFFSET {SATURN_MIDI_68K_STREAM_BATCH_COUNT_OFFSET}UL",
        f"#define SRK_R24_PROOF_TOTAL_HI_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_HI_OFFSET}UL",
        f"#define SRK_R24_PROOF_TOTAL_LO_OFFSET {SATURN_MIDI_68K_STREAM_TOTAL_LO_OFFSET}UL",
        f"#define SRK_R24_PROOF_LAST_ERROR_OFFSET {SATURN_MIDI_68K_STREAM_LAST_ERROR_OFFSET}UL",
        f"#define SRK_R24_PROOF_SERVICE_MAGIC 0x{SATURN_MIDI_68K_STREAM_SERVICE_MAGIC:04X}u",
        f"#define SRK_R24_PROOF_SERVICE_VERSION {SATURN_MIDI_68K_STREAM_SERVICE_VERSION}u",
        f"#define SRK_R24_PROOF_STREAM_ERROR 0x{SATURN_MIDI_68K_STREAM_FLAG_ERROR:04X}u",
        f"#define SRK_R24_PROOF_VOICE_ADDRESS 0x{SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS:08X}UL",
        f"#define SRK_R24_PROOF_SUMMARY_ADDRESS 0x{SATURN_MIDI_68K_STATE_ADDRESS:08X}UL",
        f"#define SRK_R24_PROOF_CONTROLLER_ADDRESS 0x{SATURN_MIDI_68K_CONTROLLER_ADDRESS:08X}UL",
        f"#define SRK_R24_PROOF_ACTIVE_ADDRESS 0x{SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:08X}UL",
        f"#define SRK_R24_PROOF_TVMD (*(volatile unsigned short *)0x{SATURN_MIDI_68K_R24_VDP2_TVMD_ADDRESS:08X}UL)",
        f"#define SRK_R24_PROOF_TVSTAT (*(volatile unsigned short *)0x{SATURN_MIDI_68K_R24_VDP2_TVSTAT_ADDRESS:08X}UL)",
        f"#define SRK_R24_PROOF_FRT_TCR (*(volatile unsigned char *)0x{SATURN_MIDI_68K_R24_FRT_TCR_ADDRESS:08X}UL)",
        f"#define SRK_R24_CLOCK_NTSC_A {SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ}UL",
        f"#define SRK_R24_CLOCK_NTSC_B {SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ}UL",
        f"#define SRK_R24_CLOCK_PAL_A {SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ}UL",
        f"#define SRK_R24_CLOCK_PAL_B {SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ}UL",
        f"#define SRK_R24_PROOF_DURATION_US {duration}UL",
        f"#define SRK_R24_PROOF_TIMEOUT_US {timeout}UL",
        "",
    ]
    lines.extend(_render_words("srk_r24_expected_summary", summaries))
    lines.extend(_render_words("srk_r24_expected_controllers", controllers))
    lines.extend(_render_words("srk_r24_expected_active", active))
    lines.extend(
        (
            "static unsigned short srk_r24_read(unsigned long address)",
            "{",
            "    return SRK_R24_PROOF_RAM[address >> 1];",
            "}",
            "",
            "static void srk_r24_write(unsigned long address, unsigned short value)",
            "{",
            "    SRK_R24_PROOF_RAM[address >> 1] = value;",
            "}",
            "",
            "static unsigned short srk_r24_service(unsigned long offset)",
            "{",
            "    return srk_r24_read(SRK_R24_PROOF_SERVICE + offset);",
            "}",
            "",
            "static unsigned short srk_r24_mailbox(unsigned long word_index)",
            "{",
            "    return srk_r24_read(SRK_MIDI_MAILBOX_ADDRESS + (word_index * 2UL));",
            "}",
            "",
            "static unsigned short srk_r24_voice(unsigned short word_index)",
            "{",
            "    return srk_r24_read(SRK_R24_PROOF_VOICE_ADDRESS + ((unsigned long)word_index * 2UL));",
            "}",
            "",
            "static unsigned long srk_r24_select_clock(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short tvstat;",
            "    unsigned short tvmd;",
            "    tvstat = SRK_R24_PROOF_TVSTAT;",
            "    tvmd = SRK_R24_PROOF_TVMD;",
            "    state->telemetry.clock_pal = (unsigned short)(tvstat & 0x0001u);",
            "    state->telemetry.clock_group_b = (unsigned short)(tvmd & 0x0001u);",
            "    if(state->telemetry.clock_pal){",
            "        if(state->telemetry.clock_group_b) return SRK_R24_CLOCK_PAL_B;",
            "        return SRK_R24_CLOCK_PAL_A;",
            "    }",
            "    if(state->telemetry.clock_group_b) return SRK_R24_CLOCK_NTSC_B;",
            "    return SRK_R24_CLOCK_NTSC_A;",
            "}",
            "",
            "static int srk_r24_install(void)",
            "{",
            "    unsigned long index;",
            "    for(index=0UL; index<0x0100UL; index+=2UL)",
            "        srk_r24_write(SRK_MIDI_MAILBOX_ADDRESS + index, 0u);",
            "    for(index=0UL; index<0x0200UL; index+=2UL)",
            "        srk_r24_write(SRK_R24_PROOF_SERVICE + index, 0u);",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++)",
            "        srk_r24_write(",
            "            SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL),",
            "            srk_saturn_midi_68k_r24_resident_audio_service_program[index]);",
            "    srk_r24_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS >> 16));",
            "    srk_r24_write(SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_R24_RESIDENT_AUDIO_STACK_ADDRESS & 0xFFFFUL));",
            "    srk_r24_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS,",
            "        (unsigned short)(SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS >> 16));",
            "    srk_r24_write(SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS + 2UL,",
            "        (unsigned short)(SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS & 0xFFFFUL));",
            "    for(index=0UL; index<(unsigned long)SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_WORD_COUNT; index++){",
            "        if(srk_r24_read(SRK_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS + (index * 2UL)) !=",
            "           srk_saturn_midi_68k_r24_resident_audio_service_program[index]) return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static void srk_r24_capture(SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short total_hi;",
            "    state->telemetry.flags = srk_r24_mailbox(SRK_MIDI_MB_FLAGS);",
            "    state->telemetry.read_sequence = srk_r24_mailbox(SRK_MIDI_MB_READ_SEQUENCE);",
            "    state->telemetry.read_index = srk_r24_mailbox(SRK_MIDI_MB_READ_INDEX);",
            "    state->telemetry.last_error = srk_r24_mailbox(SRK_MIDI_MB_LAST_ERROR);",
            "    state->telemetry.stream_flags = srk_r24_service(SRK_R24_PROOF_SERVICE_FLAGS_OFFSET);",
            "    state->telemetry.current_index = srk_r24_service(SRK_R24_PROOF_CURRENT_INDEX_OFFSET);",
            "    state->telemetry.batch_count = srk_r24_service(SRK_R24_PROOF_BATCH_COUNT_OFFSET);",
            "    total_hi = srk_r24_service(SRK_R24_PROOF_TOTAL_HI_OFFSET);",
            "    state->telemetry.total_processed = srk_r24_service(SRK_R24_PROOF_TOTAL_LO_OFFSET);",
            "    if(total_hi != 0u) state->telemetry.total_processed = 0xFFFFu;",
            "    state->telemetry.player_sequence = state->player.published_sequence;",
            "    state->telemetry.player_batch_index = state->player.next_batch_index;",
            "    state->telemetry.player_complete = state->player.complete;",
            "    state->telemetry.player_error = state->player.error;",
            f"    state->telemetry.voice_key_on_count = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_KEY_ON_COUNT_WORD}u);",
            f"    state->telemetry.voice_key_off_count = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_KEY_OFF_COUNT_WORD}u);",
            f"    state->telemetry.voice_busy_count = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_BUSY_COUNT_WORD}u);",
            f"    state->telemetry.voice_active_count = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_ACTIVE_COUNT_WORD}u);",
            f"    state->telemetry.voice_peak_active = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_PEAK_ACTIVE_WORD}u);",
            f"    state->telemetry.voice_last_error = srk_r24_voice({SATURN_MIDI_68K_R24_VOICE_LAST_ERROR_WORD}u);",
            "    if(state->telemetry.voice_peak_active >= 2u) state->telemetry.polyphony_seen = 1u;",
            "}",
            "",
            "static void srk_r24_restore_frt(SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    if(state->frt_configured){",
            "        SRK_R24_PROOF_FRT_TCR = state->original_tcr;",
            "        state->frt_configured = 0u;",
            "    }",
            "}",
            "",
            "static int srk_r24_verify_region(",
            "    unsigned long address, const unsigned short *expected, unsigned short count,",
            "    unsigned short region, SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short index;",
            "    unsigned short actual;",
            "    for(index=0u; index<count; index++){",
            "        actual = srk_r24_read(address + ((unsigned long)index * 2UL));",
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
            "static int srk_r24_verify_final_state(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            f"    if(!srk_r24_verify_region(SRK_R24_PROOF_SUMMARY_ADDRESS, srk_r24_expected_summary, {len(summaries)}u, {SATURN_MIDI_68K_R24_VERIFY_SUMMARY_MISMATCH}u, state)) return 0;",
            f"    if(!srk_r24_verify_region(SRK_R24_PROOF_CONTROLLER_ADDRESS, srk_r24_expected_controllers, {len(controllers)}u, {SATURN_MIDI_68K_R24_VERIFY_CONTROLLER_MISMATCH}u, state)) return 0;",
            f"    if(!srk_r24_verify_region(SRK_R24_PROOF_ACTIVE_ADDRESS, srk_r24_expected_active, {len(active)}u, {SATURN_MIDI_68K_R24_VERIFY_ACTIVE_NOTE_MISMATCH}u, state)) return 0;",
            f"    if(state->telemetry.read_sequence != {SATURN_MIDI_68K_R24_REFERENCE_BATCHES}u ||",
            f"       state->telemetry.read_index != {SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS}u ||",
            f"       state->telemetry.batch_count != {SATURN_MIDI_68K_R24_REFERENCE_BATCHES}u ||",
            f"       state->telemetry.total_processed != {SATURN_MIDI_68K_R24_REFERENCE_RECORDS}u ||",
            f"       state->telemetry.voice_key_on_count != {SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON}u ||",
            f"       state->telemetry.voice_key_off_count != {SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF}u ||",
            "       state->telemetry.voice_busy_count != 0u ||",
            "       state->telemetry.voice_active_count != 0u ||",
            f"       state->telemetry.voice_peak_active != {SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY}u ||",
            "       state->telemetry.voice_last_error != 0u ||",
            "       state->telemetry.polyphony_seen != 1u ||",
            f"       state->telemetry.player_sequence != {SATURN_MIDI_68K_R24_REFERENCE_BATCHES}u ||",
            f"       state->telemetry.player_batch_index != {SATURN_MIDI_68K_R24_REFERENCE_BATCHES}u ||",
            "       state->telemetry.player_complete != 1u ||",
            "       state->telemetry.player_error != 0u){",
            f"        state->telemetry.state_verify_status = {SATURN_MIDI_68K_R24_VERIFY_FINAL_CONTRACT_MISMATCH}u;",
            "        state->telemetry.mismatch_region = state->telemetry.state_verify_status;",
            "        return 0;",
            "    }",
            "    return 1;",
            "}",
            "",
            "static unsigned int srk_r24_fail(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state, unsigned short code)",
            "{",
            "    srk_r24_restore_frt(state);",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_ERROR}u;",
            "    if(state->telemetry.last_error == 0u) state->telemetry.last_error = code;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR;",
            "    return state->runtime_status;",
            "}",
            "",
            "void srk_saturn_midi_68k_r24_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    unsigned short *words;",
            "    unsigned long count;",
            "    if(!state) return;",
            "    words = (unsigned short *)state;",
            "    count = (unsigned long)(sizeof(*state) / sizeof(unsigned short));",
            "    while(count) words[--count] = 0u;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_NOT_STARTED}u;",
            "    srk_saturn_midi_r24_player_reset(&state->player);",
            "    srk_saturn_midi_r24_frt_reset(&state->clock);",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r24_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops;",
            "    if(!state) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted) return state->runtime_status;",
            "    state->attempted = 1u;",
            "    ops = srk_saturn_midi_68k_hardware_adapter_ops();",
            "    if(!ops || !ops->stop_sound_cpu || !ops->start_sound_cpu)",
            "        return srk_r24_fail(state, 0xE201u);",
            "    if(!ops->stop_sound_cpu()) return srk_r24_fail(state, 0xE202u);",
            "    if(!srk_r24_install()) return srk_r24_fail(state, 0xE203u);",
            "    if(!ops->start_sound_cpu()) return srk_r24_fail(state, 0xE204u);",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_RUNNING;",
            f"    state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_WAIT_BOOT}u;",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_r24_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE *state)",
            "{",
            "    int player_result;",
            "    unsigned long now_us;",
            "    if(!state || !state->attempted) return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "    state->poll_count += 1u;",
            "    srk_r24_capture(state);",
            "    if((state->telemetry.stream_flags & SRK_R24_PROOF_STREAM_ERROR) != 0u ||",
            "       srk_r24_service(SRK_R24_PROOF_LAST_ERROR_OFFSET) != 0u ||",
            "       state->telemetry.last_error != 0u || state->telemetry.voice_last_error != 0u)",
            "        return srk_r24_fail(state, 0xE210u);",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R24_PHASE_WAIT_BOOT}u){{",
            "        if(srk_r24_service(SRK_R24_PROOF_SERVICE_MAGIC_OFFSET) == SRK_R24_PROOF_SERVICE_MAGIC &&",
            "           srk_r24_service(SRK_R24_PROOF_SERVICE_VERSION_OFFSET) == SRK_R24_PROOF_SERVICE_VERSION){",
            "            state->telemetry.clock_source_hz = srk_r24_select_clock(state);",
            "            state->original_tcr = SRK_R24_PROOF_FRT_TCR;",
            "            state->frt_configured = 1u;",
            "            srk_saturn_midi_r24_frt_configure_div128();",
            "            srk_saturn_midi_r24_frt_reset(&state->clock);",
            "            srk_saturn_midi_r24_player_reset(&state->player);",
            "            now_us = srk_saturn_midi_r24_frt_sample_us(&state->clock, state->telemetry.clock_source_hz);",
            "            state->telemetry.clock_us = now_us;",
            "            player_result = srk_saturn_midi_r24_player_poll(&state->player, now_us);",
            "            if(player_result < 0) return srk_r24_fail(state, 0xE211u);",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_PLAYING}u;",
            "            srk_r24_capture(state);",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            f"    if(state->telemetry.phase == {SATURN_MIDI_68K_R24_PHASE_PLAYING}u){{",
            "        now_us = srk_saturn_midi_r24_frt_sample_us(&state->clock, state->telemetry.clock_source_hz);",
            "        state->telemetry.clock_us = now_us;",
            "        player_result = srk_saturn_midi_r24_player_poll(&state->player, now_us);",
            "        srk_r24_capture(state);",
            "        if(state->telemetry.voice_active_count >= 2u){",
            "            state->telemetry.polyphony_seen = 1u;",
            "            state->overlap_latched = 1u;",
            "        }else{",
            "            state->overlap_latched = 0u;",
            "        }",
            "        if(player_result < 0 || state->player.error != 0u)",
            "            return srk_r24_fail(state, 0xE212u);",
            "        if(now_us > SRK_R24_PROOF_TIMEOUT_US && !state->player.complete)",
            "            return srk_r24_fail(state, 0xE213u);",
            "        if(player_result == 1 || state->player.complete){",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_VERIFY_STATE}u;",
            "            srk_r24_capture(state);",
            "            if(!srk_r24_verify_final_state(state))",
            "                return srk_r24_fail(state, 0xE214u);",
            f"            state->telemetry.state_verify_status = {SATURN_MIDI_68K_R24_VERIFY_PASS}u;",
            f"            state->telemetry.phase = {SATURN_MIDI_68K_R24_PHASE_PASS}u;",
            "            srk_r24_restore_frt(state);",
            "            state->runtime_status = SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED;",
            "            return state->runtime_status;",
            "        }",
            "        return state->runtime_status;",
            "    }",
            "",
            "    return state->runtime_status;",
            "}",
            "",
        )
    )
    return "\n".join(lines)


_C_BACKSLASH = chr(92)
_R23_DEFINE = "#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1"
_R24_DEFINE = "#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1"
_R23_MENU_LABEL = '"MIDI 68K Audio Proof"'
_R24_MENU_LABEL = '"MIDI 68K Song Proof"'
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
_R23_GUARD = (
    _STREAM_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE)"
)
_R24_GUARD = (
    _R23_GUARD
    + " || "
    + _C_BACKSLASH
    + "\n    defined(SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE)"
)


def _r23_telemetry_block() -> str:
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


def _r24_telemetry_block() -> str:
    return "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.phase);",
            '    srk_midi_68k_draw_field(2, 12, 8, "Phase:");',
            "    srk_midi_68k_draw_field(10, 12, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.total_processed);",
            '    srk_midi_68k_draw_field(17, 12, 8, "Records:");',
            "    srk_midi_68k_draw_field(25, 12, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.batch_count);",
            '    srk_midi_68k_draw_field(32, 12, 5, "Bat:");',
            "    srk_midi_68k_draw_field(37, 12, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_us);",
            '    srk_midi_68k_draw_field(2, 13, 8, "Clock us:");',
            "    srk_midi_68k_draw_field(10, 13, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_source_hz);",
            '    srk_midi_68k_draw_field(23, 13, 8, "Hz:");',
            "    srk_midi_68k_draw_field(27, 13, 12, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_sequence);",
            '    srk_midi_68k_draw_field(2, 14, 8, "Seq:");',
            "    srk_midi_68k_draw_field(7, 14, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.read_index);",
            '    srk_midi_68k_draw_field(13, 14, 8, "Index:");',
            "    srk_midi_68k_draw_field(20, 14, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.player_batch_index);",
            '    srk_midi_68k_draw_field(26, 14, 8, "Pub:");',
            "    srk_midi_68k_draw_field(31, 14, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_on_count);",
            '    srk_midi_68k_draw_field(2, 15, 8, "Note On:");',
            "    srk_midi_68k_draw_field(10, 15, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_key_off_count);",
            '    srk_midi_68k_draw_field(18, 15, 8, "Off:");',
            "    srk_midi_68k_draw_field(23, 15, 6, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_active_count);",
            '    srk_midi_68k_draw_field(2, 16, 8, "Active:");',
            "    srk_midi_68k_draw_field(10, 16, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_peak_active);",
            '    srk_midi_68k_draw_field(16, 16, 8, "Peak:");',
            "    srk_midi_68k_draw_field(22, 16, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_busy_count);",
            '    srk_midi_68k_draw_field(28, 16, 8, "Busy:");',
            "    srk_midi_68k_draw_field(34, 16, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.polyphony_seen);",
            '    srk_midi_68k_draw_field(2, 17, 14, "Polyphony seen:");',
            "    srk_midi_68k_draw_field(16, 17, 4, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_pal);",
            '    srk_midi_68k_draw_field(22, 17, 5, "PAL:");',
            "    srk_midi_68k_draw_field(27, 17, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.clock_group_b);",
            '    srk_midi_68k_draw_field(31, 17, 6, "GrpB:");',
            "    srk_midi_68k_draw_field(37, 17, 3, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.state_verify_status);",
            '    srk_midi_68k_draw_field(2, 18, 14, "State verify:");',
            "    srk_midi_68k_draw_field(16, 18, 5, number);",
            "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.voice_last_error);",
            '    srk_midi_68k_draw_field(22, 18, 10, "Voice err:");',
            "    srk_midi_68k_draw_field(32, 18, 6, number);",
            "#endif",
        )
    )


def derive_r24_physical_candidate_main(r23_main: str) -> str:
    if not r23_main.startswith(_R23_DEFINE + "\n"):
        raise RuntimeError("R23 main no longer begins with the accepted audio candidate define")
    main = _R24_DEFINE + r23_main[len(_R23_DEFINE):]

    if main.count(_R23_GUARD) < 2:
        raise RuntimeError("R23 proof preprocessor guard shape changed")
    main = main.replace(_R23_GUARD, _R24_GUARD)

    r23_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_r23_physical_proof.h"',
            "#endif",
        )
    )
    r24_include = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            '#include "srk_saturn_midi_68k_r24_physical_proof.h"',
            "#endif",
        )
    )
    if main.count(r23_include) != 1:
        raise RuntimeError("R23 proof include block shape changed")
    main = main.replace(r23_include, r24_include, 1)

    r23_alias = "\n".join(
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
    r24_alias = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_R24_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            f"#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX {SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS}u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K REAL SONG"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "310 events - FRT clock - two SCSP voices"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Song PASS: 310 events / peak voices 2"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_r24_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_r24_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_r24_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(r23_alias) != 1:
        raise RuntimeError("R23 proof alias block shape changed")
    main = main.replace(r23_alias, r24_alias, 1)

    r23_telemetry = _r23_telemetry_block()
    if main.count(r23_telemetry) != 1:
        raise RuntimeError("R23 telemetry rendering shape changed")
    main = main.replace(r23_telemetry, _r24_telemetry_block(), 1)

    r23_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    r24_success = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE",
            "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
            "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
        )
    )
    if main.count(r23_success) != 1:
        raise RuntimeError("R23 success rendering shape changed")
    main = main.replace(r23_success, r24_success, 1)

    required = (
        _R24_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u",
        '"MIDI / 68K REAL SONG"',
        '"Song PASS: 310 events / peak voices 2"',
        "srk_saturn_midi_68k_r24_physical_proof_begin",
        "telemetry.clock_source_hz",
        "telemetry.voice_key_on_count",
        "telemetry.voice_peak_active",
        "telemetry.polyphony_seen",
    )
    for marker in required:
        if marker not in main:
            raise RuntimeError(f"derived R24 candidate main missing marker: {marker}")
    return main


def derive_r24_physical_candidate_menu(r23_menu: str) -> str:
    if r23_menu.count(_R23_MENU_LABEL) != 1:
        raise RuntimeError("R23 audio proof menu label is no longer isolated")
    menu = r23_menu.replace(_R23_MENU_LABEL, _R24_MENU_LABEL, 1)
    if menu.count(_R24_MENU_LABEL) != 1:
        raise RuntimeError("R24 song proof menu label derivation failed")
    return menu
