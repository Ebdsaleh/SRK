"""R26 Space Spectre SH-2 producer C89 renderer.

R26 reuses the accepted R24 mailbox/clock/refill contract, but renders the
9,154-record Double Impact program into 287 strict 32-record batches with R26
symbols so the accepted R24 physical baseline remains untouched.
"""

from __future__ import annotations

import re

from .midi_68k_r24_song import batch_saturn_midi_r24_program
from .midi_program import SaturnMidiProgram


SATURN_MIDI_68K_R26_PLAYER_ERROR_CLOCK_BACKWARDS = 1
SATURN_MIDI_68K_R26_PLAYER_ERROR_CONTRACT = 3
_C_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class SaturnMidi68KR26PlayerError(RuntimeError):
    """Raised when the R26 producer cannot be rendered safely."""


def render_saturn_midi_68k_r26_player_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R26_PLAYER_H",
            "#define SRK_SATURN_MIDI_68K_R26_PLAYER_H",
            "",
            "typedef struct SRK_MIDI_R26_PLAYER_STATE {",
            "    unsigned short published_sequence;",
            "    unsigned short next_batch_index;",
            "    unsigned short batch_count;",
            "    unsigned short complete;",
            "    unsigned short error;",
            "    unsigned short clock_initialized;",
            "    unsigned long last_clock_us;",
            "} SRK_MIDI_R26_PLAYER_STATE;",
            "",
            "void srk_saturn_midi_r26_player_reset(SRK_MIDI_R26_PLAYER_STATE *state);",
            "int srk_saturn_midi_r26_player_poll(SRK_MIDI_R26_PLAYER_STATE *state, unsigned long now_us);",
            "",
            "#endif",
            "",
        )
    )


def _render_batch(batch, symbol_prefix: str) -> list[str]:
    lines = [
        f"static const SRK_SATURN_MIDI_EVENT {symbol_prefix}_batch_{batch.sequence}[] = {{"
    ]
    for record in batch.records:
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
    lines.extend(("};", ""))
    return lines


def render_saturn_midi_68k_r26_player_source(
    program: SaturnMidiProgram,
    *,
    symbol_prefix: str = "srk_r26_space_spectre",
) -> str:
    if _C_SYMBOL_RE.fullmatch(symbol_prefix) is None:
        raise SaturnMidi68KR26PlayerError(f"invalid R26 C symbol prefix: {symbol_prefix!r}")
    batches = batch_saturn_midi_r24_program(program)
    if not batches or len(batches) > 0xFFFF:
        raise SaturnMidi68KR26PlayerError("R26 batch count is outside 1..65535")

    lines = [
        '#include "srk_saturn_midi_68k_r26_player.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        "",
    ]
    for batch in batches:
        lines.extend(_render_batch(batch, symbol_prefix))

    lines.extend(
        (
            f"#define SRK_R26_BATCH_COUNT {len(batches)}u",
            f"#define SRK_R26_DURATION_US {program.duration_us}UL",
            "",
            "static int srk_r26_publish_batch(unsigned short index)",
            "{",
            "    switch(index){",
        )
    )
    for index, batch in enumerate(batches):
        lines.extend(
            (
                f"    case {index}u:",
                f"        return srk_saturn_midi_stream_batch_publish({symbol_prefix}_batch_{batch.sequence}, {len(batch.records)}u, {batch.sequence}u);",
            )
        )
    lines.extend(
        (
            "    default:",
            "        return 0;",
            "    }",
            "}",
            "",
            "void srk_saturn_midi_r26_player_reset(SRK_MIDI_R26_PLAYER_STATE *state)",
            "{",
            "    if(!state) return;",
            "    state->published_sequence = 0u;",
            "    state->next_batch_index = 0u;",
            "    state->batch_count = SRK_R26_BATCH_COUNT;",
            "    state->complete = 0u;",
            "    state->error = 0u;",
            "    state->clock_initialized = 0u;",
            "    state->last_clock_us = 0UL;",
            "}",
            "",
            "int srk_saturn_midi_r26_player_poll(SRK_MIDI_R26_PLAYER_STATE *state, unsigned long now_us)",
            "{",
            "    unsigned short sequence;",
            "    if(!state || state->error != 0u) return -1;",
            "    if(state->complete) return 1;",
            "    if(state->clock_initialized && now_us < state->last_clock_us){",
            f"        state->error = {SATURN_MIDI_68K_R26_PLAYER_ERROR_CLOCK_BACKWARDS}u;",
            "        return -1;",
            "    }",
            "    state->clock_initialized = 1u;",
            "    state->last_clock_us = now_us;",
            "    srk_saturn_midi_stream_clock_publish(now_us);",
            "",
            "    if(state->published_sequence != 0u){",
            "        if(!srk_saturn_midi_stream_batch_acknowledged(state->published_sequence))",
            "            return 0;",
            "        if(state->next_batch_index >= state->batch_count){",
            "            state->complete = 1u;",
            "            return 1;",
            "        }",
            "    }",
            "",
            "    if(state->next_batch_index >= state->batch_count){",
            f"        state->error = {SATURN_MIDI_68K_R26_PLAYER_ERROR_CONTRACT}u;",
            "        return -1;",
            "    }",
            "    sequence = (unsigned short)(state->next_batch_index + 1u);",
            "    if(!srk_r26_publish_batch(state->next_batch_index)) return 0;",
            "    state->published_sequence = sequence;",
            "    state->next_batch_index = (unsigned short)(state->next_batch_index + 1u);",
            "    return 0;",
            "}",
            "",
        )
    )
    return "\n".join(lines)
