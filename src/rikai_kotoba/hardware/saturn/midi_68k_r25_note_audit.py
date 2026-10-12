"""R25 source/model audit for MIDI note duration and release-tail capacity.

R24 physically proved complete real-SMF transport, timing and two-voice playback.
R25 separates MIDI key ownership from audible SCSP release tails so a normal
Note Off no longer has to become an immediate hard mute.

This module performs no hardware I/O.  It derives exact Note On/Off spans from
an SRKM v1 program and models the extra slot pressure caused by bounded release
tails.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from statistics import median

from .midi_program import SaturnMidiOpcode, SaturnMidiProgram


SATURN_MIDI_68K_R25_OWNED_SLOTS = 4
SATURN_MIDI_68K_R25_TARGET_RELEASE_US = 120_000
SATURN_MIDI_68K_R25_RELEASE_CAPACITY_AUDIT_US = 500_000


class SaturnMidi68KR25NoteAuditError(RuntimeError):
    """Raised when an SRKM program cannot form deterministic note spans."""


@dataclass(frozen=True)
class SaturnMidi68KR25NoteSpan:
    channel: int
    note: int
    velocity: int
    start_us: int
    end_us: int

    @property
    def duration_us(self) -> int:
        return self.end_us - self.start_us


@dataclass(frozen=True)
class SaturnMidi68KR25NoteAudit:
    spans: tuple[SaturnMidi68KR25NoteSpan, ...]
    minimum_duration_us: int
    median_duration_us: float
    maximum_duration_us: int
    shorter_than_250ms: int
    release_target_us: int
    peak_with_release_target: int
    release_capacity_audit_us: int
    peak_with_release_capacity_audit: int


def build_saturn_midi_68k_r25_note_spans(
    program: SaturnMidiProgram,
) -> tuple[SaturnMidi68KR25NoteSpan, ...]:
    """Pair normalized Note On/Off records without changing their timestamps."""

    active: dict[tuple[int, int], deque[tuple[int, int]]] = defaultdict(deque)
    spans: list[SaturnMidi68KR25NoteSpan] = []

    for record in program.records:
        key = (record.channel, record.data0)
        is_note_on = record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 != 0
        is_note_off = record.opcode == SaturnMidiOpcode.NOTE_OFF or (
            record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 == 0
        )
        if is_note_on:
            active[key].append((record.time_us, record.data1))
            continue
        if not is_note_off:
            continue
        if not active[key]:
            raise SaturnMidi68KR25NoteAuditError(
                f"orphan Note Off for channel {record.channel} note {record.data0}"
            )
        start_us, velocity = active[key].popleft()
        if record.time_us < start_us:
            raise SaturnMidi68KR25NoteAuditError("Note Off occurs before Note On")
        spans.append(
            SaturnMidi68KR25NoteSpan(
                channel=record.channel,
                note=record.data0,
                velocity=velocity,
                start_us=start_us,
                end_us=record.time_us,
            )
        )

    hanging = [key for key, queue in active.items() if queue]
    if hanging:
        raise SaturnMidi68KR25NoteAuditError(f"unreleased MIDI notes remain: {hanging!r}")
    if not spans:
        raise SaturnMidi68KR25NoteAuditError("program contains no complete note spans")
    return tuple(sorted(spans, key=lambda span: (span.start_us, span.channel, span.note)))


def peak_saturn_midi_68k_r25_voice_pressure(
    spans: tuple[SaturnMidi68KR25NoteSpan, ...],
    *,
    release_us: int,
) -> int:
    """Return active+releasing peak when each Note Off owns its slot for release_us."""

    if release_us < 0:
        raise SaturnMidi68KR25NoteAuditError("release_us must be non-negative")
    edges: list[tuple[int, int]] = []
    for span in spans:
        edges.append((span.start_us, 1))
        edges.append((span.end_us + release_us, -1))
    # Free an ending tail before allocating a note that starts at the same time.
    edges.sort(key=lambda edge: (edge[0], edge[1]))
    active = 0
    peak = 0
    for _time_us, delta in edges:
        active += delta
        if active < 0:
            raise SaturnMidi68KR25NoteAuditError("release-tail pressure underflow")
        peak = max(peak, active)
    if active != 0:
        raise SaturnMidi68KR25NoteAuditError("release-tail pressure did not return to zero")
    return peak


def audit_saturn_midi_68k_r25_note_spans(
    program: SaturnMidiProgram,
    *,
    target_release_us: int = SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
    capacity_audit_us: int = SATURN_MIDI_68K_R25_RELEASE_CAPACITY_AUDIT_US,
) -> SaturnMidi68KR25NoteAudit:
    spans = build_saturn_midi_68k_r25_note_spans(program)
    durations = tuple(span.duration_us for span in spans)
    if min(durations) <= 0:
        raise SaturnMidi68KR25NoteAuditError("zero-length note span is not accepted for R25")
    return SaturnMidi68KR25NoteAudit(
        spans=spans,
        minimum_duration_us=min(durations),
        median_duration_us=float(median(durations)),
        maximum_duration_us=max(durations),
        shorter_than_250ms=sum(duration < 250_000 for duration in durations),
        release_target_us=target_release_us,
        peak_with_release_target=peak_saturn_midi_68k_r25_voice_pressure(
            spans, release_us=target_release_us
        ),
        release_capacity_audit_us=capacity_audit_us,
        peak_with_release_capacity_audit=peak_saturn_midi_68k_r25_voice_pressure(
            spans, release_us=capacity_audit_us
        ),
    )
