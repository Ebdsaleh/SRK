"""Deterministic timing and channel-state scheduling for parsed MIDI files.

This module consumes the platform-neutral SMF model from ``formats.midi`` and
produces a normalized event timeline.  It deliberately contains no Saturn
hardware policy so the same schedule can feed diagnostics, Mjolnir, the flight
recorder, or later replacement tooling.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Optional

from rikai_kotoba.formats.midi import MidiEvent, MidiFile, merge_midi_events


MIDI_DEFAULT_TEMPO_US_PER_QUARTER = 500000
MIDI_CHANNEL_COUNT = 16
MIDI_PITCH_BEND_CENTER = 8192


class MidiTimingError(RuntimeError):
    """Raised when one MIDI file cannot be represented by one playback clock."""


@dataclass(frozen=True)
class MidiTempoPoint:
    """One PPQN tempo segment boundary with exact accumulated time."""

    tick: int
    elapsed_us: Fraction
    us_per_quarter: int

    @property
    def time_us(self) -> int:
        """Return deterministic whole microseconds, rounded toward zero."""

        return int(self.elapsed_us)


@dataclass(frozen=True)
class MidiTempoMap:
    """Piecewise PPQN tempo map for one merged MIDI playback timeline."""

    ticks_per_quarter: int
    points: tuple[MidiTempoPoint, ...]


@dataclass(frozen=True)
class MidiChannelState:
    """Normalized channel state known explicitly at one scheduled event."""

    bank_msb: Optional[int] = None
    bank_lsb: Optional[int] = None
    program: Optional[int] = None
    volume: Optional[int] = None
    pan: Optional[int] = None
    expression: Optional[int] = None
    sustain: bool = False
    pitch_bend: int = MIDI_PITCH_BEND_CENTER


@dataclass(frozen=True)
class MidiScheduledEvent:
    """One merged MIDI event with deterministic wall-clock placement.

    ``channel_state`` is the state *after* applying this event when it changes a
    channel controller/program value.  For note events it is therefore the
    complete state active when the note occurs.
    """

    time_us: int
    track_index: int
    event_index: int
    event: MidiEvent
    channel_state: Optional[MidiChannelState]


def _require_single_timeline(midi: MidiFile) -> int:
    if midi.header.format_type == 2:
        raise MidiTimingError(
            "MIDI format 2 contains independent track timelines; schedule each sequence separately"
        )
    if midi.header.uses_smpte_timing:
        raise MidiTimingError(
            "SMPTE-timed MIDI is preserved by the parser but is not yet a PPQN tempo-map timeline"
        )
    ticks_per_quarter = midi.header.ticks_per_quarter
    if ticks_per_quarter is None or ticks_per_quarter <= 0:
        raise MidiTimingError("MIDI PPQN division must be positive")
    return ticks_per_quarter


def build_midi_tempo_map(midi: MidiFile) -> MidiTempoMap:
    """Build an exact piecewise tempo map for one SMF format 0/1 PPQN timeline."""

    ticks_per_quarter = _require_single_timeline(midi)
    tempo = MIDI_DEFAULT_TEMPO_US_PER_QUARTER
    previous_tick = 0
    elapsed = Fraction(0, 1)
    points: list[MidiTempoPoint] = [
        MidiTempoPoint(
            tick=0,
            elapsed_us=elapsed,
            us_per_quarter=tempo,
        )
    ]

    for item in merge_midi_events(midi):
        event = item.event
        if event.kind != "set_tempo":
            continue

        next_tempo = event.tempo_us_per_quarter
        if next_tempo is None or next_tempo <= 0:
            raise MidiTimingError("MIDI tempo must be a positive microseconds-per-quarter value")

        elapsed += Fraction(
            (event.tick - previous_tick) * tempo,
            ticks_per_quarter,
        )
        previous_tick = event.tick
        tempo = next_tempo
        point = MidiTempoPoint(
            tick=event.tick,
            elapsed_us=elapsed,
            us_per_quarter=tempo,
        )

        # Multiple tempo events at one tick have no elapsed interval between
        # them.  The last one in deterministic merged order owns the following
        # segment, so replace rather than duplicate that boundary.
        if points[-1].tick == event.tick:
            points[-1] = point
        else:
            points.append(point)

    return MidiTempoMap(
        ticks_per_quarter=ticks_per_quarter,
        points=tuple(points),
    )


def midi_tick_to_microseconds(tempo_map: MidiTempoMap, tick: int) -> int:
    """Convert one absolute MIDI tick to deterministic whole microseconds."""

    if tick < 0:
        raise MidiTimingError("MIDI tick must not be negative")
    if not tempo_map.points:
        raise MidiTimingError("MIDI tempo map has no points")

    point = tempo_map.points[0]
    for candidate in tempo_map.points[1:]:
        if candidate.tick > tick:
            break
        point = candidate

    elapsed = point.elapsed_us + Fraction(
        (tick - point.tick) * point.us_per_quarter,
        tempo_map.ticks_per_quarter,
    )
    return int(elapsed)


def _apply_channel_event(
    state: MidiChannelState,
    event: MidiEvent,
) -> MidiChannelState:
    if event.kind == "program_change" and len(event.data) == 1:
        return replace(state, program=event.data[0])

    if event.kind == "pitch_bend":
        bend = event.pitch_bend
        if bend is not None:
            return replace(state, pitch_bend=bend)
        return state

    if event.kind != "control_change" or len(event.data) != 2:
        return state

    controller, value = event.data
    if controller == 0:
        return replace(state, bank_msb=value)
    if controller == 32:
        return replace(state, bank_lsb=value)
    if controller == 7:
        return replace(state, volume=value)
    if controller == 10:
        return replace(state, pan=value)
    if controller == 11:
        return replace(state, expression=value)
    if controller == 64:
        return replace(state, sustain=value >= 64)
    return state


def build_midi_playback_schedule(midi: MidiFile) -> tuple[MidiScheduledEvent, ...]:
    """Return all merged events with timing and normalized per-channel state."""

    tempo_map = build_midi_tempo_map(midi)
    channel_states = [MidiChannelState() for _ in range(MIDI_CHANNEL_COUNT)]
    scheduled: list[MidiScheduledEvent] = []

    for item in merge_midi_events(midi):
        event = item.event
        channel_state: Optional[MidiChannelState] = None
        if event.channel is not None:
            if event.channel < 0 or event.channel >= MIDI_CHANNEL_COUNT:
                raise MidiTimingError(f"MIDI channel out of range: {event.channel}")
            channel_states[event.channel] = _apply_channel_event(
                channel_states[event.channel],
                event,
            )
            channel_state = channel_states[event.channel]

        scheduled.append(
            MidiScheduledEvent(
                time_us=midi_tick_to_microseconds(tempo_map, event.tick),
                track_index=item.track_index,
                event_index=item.event_index,
                event=event,
                channel_state=channel_state,
            )
        )

    return tuple(scheduled)
