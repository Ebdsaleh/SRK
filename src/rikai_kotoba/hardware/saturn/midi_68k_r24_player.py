"""R24 complete-song SH-2 producer model and C89 renderer.

The player consumes a real SRKM program split into the accepted 32-record queue
batches.  It publishes a monotonic microsecond clock on every poll and advances
only after the resident MC68EC000 acknowledges the currently published batch.
The physical clock is intentionally injected by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from .midi_68k_r24_song import (
    SaturnMidi68KR24Batch,
    batch_saturn_midi_r24_program,
)
from .midi_program import SaturnMidiProgram


SATURN_MIDI_68K_R24_PLAYER_VERSION = 1
SATURN_MIDI_68K_R24_PLAYER_ERROR_NONE = 0
SATURN_MIDI_68K_R24_PLAYER_ERROR_CLOCK_BACKWARDS = 1
SATURN_MIDI_68K_R24_PLAYER_ERROR_BATCH_PUBLISH = 2
SATURN_MIDI_68K_R24_PLAYER_ERROR_CONTRACT = 3


class SaturnMidi68KR24PlayerError(RuntimeError):
    """Raised when the complete-song producer violates its queue/clock contract."""


@dataclass(frozen=True)
class SaturnMidi68KR24PlayerState:
    batches: tuple[SaturnMidi68KR24Batch, ...]
    published_sequence: int = 0
    next_batch_index: int = 0
    last_clock_us: int = 0
    clock_initialized: bool = False
    complete: bool = False
    error: int = SATURN_MIDI_68K_R24_PLAYER_ERROR_NONE


@dataclass(frozen=True)
class SaturnMidi68KR24PlayerStep:
    state: SaturnMidi68KR24PlayerState
    publish_sequence: int | None
    publish_records: tuple | None


def default_saturn_midi_68k_r24_player_state(
    program: SaturnMidiProgram,
) -> SaturnMidi68KR24PlayerState:
    batches = batch_saturn_midi_r24_program(program)
    if not batches:
        raise SaturnMidi68KR24PlayerError("R24 player requires at least one batch")
    return SaturnMidi68KR24PlayerState(batches=batches)


def step_saturn_midi_68k_r24_player(
    state: SaturnMidi68KR24PlayerState,
    now_us: int,
    acknowledged_sequence: int,
) -> SaturnMidi68KR24PlayerStep:
    """Return the next batch publication action for one producer poll."""

    if now_us < 0 or now_us > 0xFFFFFFFF:
        raise SaturnMidi68KR24PlayerError("R24 player clock is outside 32-bit SRKM range")
    if acknowledged_sequence < 0 or acknowledged_sequence > 0xFFFF:
        raise SaturnMidi68KR24PlayerError("R24 acknowledged sequence is outside 16-bit range")
    if state.error != SATURN_MIDI_68K_R24_PLAYER_ERROR_NONE or state.complete:
        return SaturnMidi68KR24PlayerStep(state=state, publish_sequence=None, publish_records=None)
    if state.clock_initialized and now_us < state.last_clock_us:
        failed = SaturnMidi68KR24PlayerState(
            batches=state.batches,
            published_sequence=state.published_sequence,
            next_batch_index=state.next_batch_index,
            last_clock_us=state.last_clock_us,
            clock_initialized=True,
            complete=False,
            error=SATURN_MIDI_68K_R24_PLAYER_ERROR_CLOCK_BACKWARDS,
        )
        return SaturnMidi68KR24PlayerStep(failed, None, None)

    updated = SaturnMidi68KR24PlayerState(
        batches=state.batches,
        published_sequence=state.published_sequence,
        next_batch_index=state.next_batch_index,
        last_clock_us=now_us,
        clock_initialized=True,
        complete=state.complete,
        error=state.error,
    )

    if updated.published_sequence != 0:
        if acknowledged_sequence != updated.published_sequence:
            return SaturnMidi68KR24PlayerStep(updated, None, None)
        if updated.next_batch_index >= len(updated.batches):
            done = SaturnMidi68KR24PlayerState(
                batches=updated.batches,
                published_sequence=updated.published_sequence,
                next_batch_index=updated.next_batch_index,
                last_clock_us=updated.last_clock_us,
                clock_initialized=True,
                complete=True,
                error=SATURN_MIDI_68K_R24_PLAYER_ERROR_NONE,
            )
            return SaturnMidi68KR24PlayerStep(done, None, None)

    if updated.next_batch_index >= len(updated.batches):
        raise SaturnMidi68KR24PlayerError("R24 player exhausted batches without final acknowledgement")

    batch = updated.batches[updated.next_batch_index]
    if batch.sequence != updated.next_batch_index + 1:
        raise SaturnMidi68KR24PlayerError("R24 batch sequence/index contract changed")
    published = SaturnMidi68KR24PlayerState(
        batches=updated.batches,
        published_sequence=batch.sequence,
        next_batch_index=updated.next_batch_index + 1,
        last_clock_us=updated.last_clock_us,
        clock_initialized=True,
        complete=False,
        error=SATURN_MIDI_68K_R24_PLAYER_ERROR_NONE,
    )
    return SaturnMidi68KR24PlayerStep(
        state=published,
        publish_sequence=batch.sequence,
        publish_records=batch.records,
    )


def validate_saturn_midi_68k_r24_complete_player(program: SaturnMidiProgram) -> None:
    """Model all ten publications/acknowledgements and the final song boundary."""

    state = default_saturn_midi_68k_r24_player_state(program)
    acknowledged = 0
    publications: list[int] = []

    # Poll at each batch's final timestamp.  The player only decides publication;
    # the resident timestamp scheduler remains authoritative for record execution.
    while not state.complete:
        if state.next_batch_index < len(state.batches):
            now_us = state.batches[state.next_batch_index].last_time_us
        else:
            now_us = program.duration_us
        step = step_saturn_midi_68k_r24_player(state, now_us, acknowledged)
        state = step.state
        if step.publish_sequence is not None:
            publications.append(step.publish_sequence)
            acknowledged = step.publish_sequence
        elif not state.complete and state.published_sequence:
            acknowledged = state.published_sequence

    if tuple(publications) != tuple(range(1, len(state.batches) + 1)):
        raise SaturnMidi68KR24PlayerError(
            f"R24 complete-song publication sequence changed: {publications!r}"
        )
    if state.published_sequence != len(state.batches) or state.error != 0:
        raise SaturnMidi68KR24PlayerError("R24 complete-song final producer state is invalid")


_C_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def render_saturn_midi_68k_r24_player_header() -> str:
    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_R24_PLAYER_H",
            "#define SRK_SATURN_MIDI_68K_R24_PLAYER_H",
            "",
            "typedef struct SRK_MIDI_R24_PLAYER_STATE {",
            "    unsigned short published_sequence;",
            "    unsigned short next_batch_index;",
            "    unsigned short batch_count;",
            "    unsigned short complete;",
            "    unsigned short error;",
            "    unsigned short clock_initialized;",
            "    unsigned long last_clock_us;",
            "} SRK_MIDI_R24_PLAYER_STATE;",
            "",
            "void srk_saturn_midi_r24_player_reset(SRK_MIDI_R24_PLAYER_STATE *state);",
            "int srk_saturn_midi_r24_player_poll(SRK_MIDI_R24_PLAYER_STATE *state, unsigned long now_us);",
            "",
            "#endif",
            "",
        )
    )


def _render_batch(batch: SaturnMidi68KR24Batch, symbol_prefix: str) -> list[str]:
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


def render_saturn_midi_68k_r24_player_source(
    program: SaturnMidiProgram,
    *,
    symbol_prefix: str = "srk_r24_song",
) -> str:
    """Render the complete real song and strict 10-batch refill state machine."""

    if _C_SYMBOL_RE.fullmatch(symbol_prefix) is None:
        raise SaturnMidi68KR24PlayerError(f"invalid R24 C symbol prefix: {symbol_prefix!r}")
    batches = batch_saturn_midi_r24_program(program)
    if len(batches) > 0xFFFF:
        raise SaturnMidi68KR24PlayerError("R24 rendered batch count exceeds 16-bit state")

    lines = [
        '#include "srk_saturn_midi_68k_r24_player.h"',
        '#include "srk_saturn_midi_68k_stream_service.h"',
        "",
    ]
    for batch in batches:
        lines.extend(_render_batch(batch, symbol_prefix))

    lines.extend(
        (
            f"#define SRK_R24_BATCH_COUNT {len(batches)}u",
            f"#define SRK_R24_DURATION_US {program.duration_us}UL",
            "",
            "static int srk_r24_publish_batch(unsigned short index)",
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
            "void srk_saturn_midi_r24_player_reset(SRK_MIDI_R24_PLAYER_STATE *state)",
            "{",
            "    if(!state) return;",
            "    state->published_sequence = 0u;",
            "    state->next_batch_index = 0u;",
            "    state->batch_count = SRK_R24_BATCH_COUNT;",
            "    state->complete = 0u;",
            "    state->error = 0u;",
            "    state->clock_initialized = 0u;",
            "    state->last_clock_us = 0UL;",
            "}",
            "",
            "int srk_saturn_midi_r24_player_poll(SRK_MIDI_R24_PLAYER_STATE *state, unsigned long now_us)",
            "{",
            "    unsigned short sequence;",
            "    if(!state || state->error != 0u) return -1;",
            "    if(state->complete) return 1;",
            "    if(state->clock_initialized && now_us < state->last_clock_us){",
            f"        state->error = {SATURN_MIDI_68K_R24_PLAYER_ERROR_CLOCK_BACKWARDS}u;",
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
            f"        state->error = {SATURN_MIDI_68K_R24_PLAYER_ERROR_CONTRACT}u;",
            "        return -1;",
            "    }",
            "    sequence = (unsigned short)(state->next_batch_index + 1u);",
            "    if(!srk_r24_publish_batch(state->next_batch_index))",
            "        return 0;",
            "    state->published_sequence = sequence;",
            "    state->next_batch_index = (unsigned short)(state->next_batch_index + 1u);",
            "    return 0;",
            "}",
            "",
        )
    )
    return "\n".join(lines)
