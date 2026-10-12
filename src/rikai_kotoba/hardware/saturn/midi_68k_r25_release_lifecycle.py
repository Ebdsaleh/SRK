"""Deterministic R25 held/releasing SCSP-slot lifecycle model.

R24 treats MIDI Note Off as immediate slot release and mixer mute.  R25 keeps
logical MIDI-key ownership separate from physical SCSP-slot ownership: Note Off
ends the key, starts a bounded release tail, and only a later clock advance
returns the slot to the free pool.

This module is a source/model gate.  It performs no hardware I/O and does not
claim that the target release duration maps to any particular SCSP RR value.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

from .midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
)
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram


class SaturnMidi68KR25SlotPhase(IntEnum):
    FREE = 0
    HELD = 1
    RELEASING = 2


class SaturnMidi68KR25ReleaseLifecycleError(RuntimeError):
    """Raised when the four-slot release lifecycle loses deterministic state."""


@dataclass(frozen=True)
class SaturnMidi68KR25ReleaseSlot:
    index: int
    phase: SaturnMidi68KR25SlotPhase = SaturnMidi68KR25SlotPhase.FREE
    channel: int = -1
    note: int = -1
    velocity: int = 0
    generation: int = 0
    release_started_us: int = 0
    release_deadline_us: int = 0


@dataclass(frozen=True)
class SaturnMidi68KR25ReleaseTelemetry:
    note_on_count: int = 0
    note_off_count: int = 0
    release_started_count: int = 0
    release_completed_count: int = 0
    release_cancelled_count: int = 0
    retrigger_count: int = 0
    busy_count: int = 0
    peak_held: int = 0
    peak_releasing: int = 0
    peak_owned: int = 0


@dataclass(frozen=True)
class SaturnMidi68KR25ReleaseState:
    now_us: int
    generation: int
    slots: tuple[SaturnMidi68KR25ReleaseSlot, ...]
    telemetry: SaturnMidi68KR25ReleaseTelemetry

    @property
    def held_count(self) -> int:
        return sum(slot.phase == SaturnMidi68KR25SlotPhase.HELD for slot in self.slots)

    @property
    def releasing_count(self) -> int:
        return sum(
            slot.phase == SaturnMidi68KR25SlotPhase.RELEASING for slot in self.slots
        )

    @property
    def owned_count(self) -> int:
        return self.held_count + self.releasing_count


def build_saturn_midi_68k_r25_release_state(
    *, owned_slots: int = SATURN_MIDI_68K_R25_OWNED_SLOTS
) -> SaturnMidi68KR25ReleaseState:
    if owned_slots <= 0 or owned_slots > 32:
        raise SaturnMidi68KR25ReleaseLifecycleError("owned_slots must be within 1..32")
    return SaturnMidi68KR25ReleaseState(
        now_us=0,
        generation=0,
        slots=tuple(SaturnMidi68KR25ReleaseSlot(index=index) for index in range(owned_slots)),
        telemetry=SaturnMidi68KR25ReleaseTelemetry(),
    )


def _update_peaks(
    state: SaturnMidi68KR25ReleaseState,
) -> SaturnMidi68KR25ReleaseState:
    telemetry = replace(
        state.telemetry,
        peak_held=max(state.telemetry.peak_held, state.held_count),
        peak_releasing=max(state.telemetry.peak_releasing, state.releasing_count),
        peak_owned=max(state.telemetry.peak_owned, state.owned_count),
    )
    return replace(state, telemetry=telemetry)


def advance_saturn_midi_68k_r25_releases(
    state: SaturnMidi68KR25ReleaseState,
    now_us: int,
) -> SaturnMidi68KR25ReleaseState:
    """Retire every release whose reviewed deadline is due at ``now_us``."""

    if now_us < state.now_us:
        raise SaturnMidi68KR25ReleaseLifecycleError("release clock moved backwards")
    completed = 0
    slots: list[SaturnMidi68KR25ReleaseSlot] = []
    for slot in state.slots:
        if (
            slot.phase == SaturnMidi68KR25SlotPhase.RELEASING
            and now_us >= slot.release_deadline_us
        ):
            completed += 1
            slots.append(SaturnMidi68KR25ReleaseSlot(index=slot.index))
        else:
            slots.append(slot)
    telemetry = replace(
        state.telemetry,
        release_completed_count=state.telemetry.release_completed_count + completed,
    )
    return _update_peaks(
        replace(state, now_us=now_us, slots=tuple(slots), telemetry=telemetry)
    )


def note_on_saturn_midi_68k_r25_release(
    state: SaturnMidi68KR25ReleaseState,
    *,
    now_us: int,
    channel: int,
    note: int,
    velocity: int,
) -> SaturnMidi68KR25ReleaseState:
    state = advance_saturn_midi_68k_r25_releases(state, now_us)
    if not 0 <= channel <= 15 or not 0 <= note <= 127 or not 1 <= velocity <= 127:
        raise SaturnMidi68KR25ReleaseLifecycleError("invalid Note On payload")

    matching = next(
        (
            slot
            for slot in state.slots
            if slot.phase != SaturnMidi68KR25SlotPhase.FREE
            and slot.channel == channel
            and slot.note == note
        ),
        None,
    )
    selected = matching or next(
        (slot for slot in state.slots if slot.phase == SaturnMidi68KR25SlotPhase.FREE),
        None,
    )
    if selected is None:
        return replace(
            state,
            telemetry=replace(
                state.telemetry,
                note_on_count=state.telemetry.note_on_count + 1,
                busy_count=state.telemetry.busy_count + 1,
            ),
        )

    generation = (state.generation + 1) & 0xFFFF
    if generation == 0:
        generation = 1
    slots = list(state.slots)
    slots[selected.index] = SaturnMidi68KR25ReleaseSlot(
        index=selected.index,
        phase=SaturnMidi68KR25SlotPhase.HELD,
        channel=channel,
        note=note,
        velocity=velocity,
        generation=generation,
    )
    telemetry = replace(
        state.telemetry,
        note_on_count=state.telemetry.note_on_count + 1,
        retrigger_count=state.telemetry.retrigger_count
        + (1 if matching is not None else 0),
        release_cancelled_count=state.telemetry.release_cancelled_count
        + (
            1
            if matching is not None
            and matching.phase == SaturnMidi68KR25SlotPhase.RELEASING
            else 0
        ),
    )
    return _update_peaks(
        replace(state, generation=generation, slots=tuple(slots), telemetry=telemetry)
    )


def note_off_saturn_midi_68k_r25_release(
    state: SaturnMidi68KR25ReleaseState,
    *,
    now_us: int,
    channel: int,
    note: int,
    release_us: int = SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
) -> SaturnMidi68KR25ReleaseState:
    state = advance_saturn_midi_68k_r25_releases(state, now_us)
    if release_us <= 0:
        raise SaturnMidi68KR25ReleaseLifecycleError("release_us must be positive")
    selected = next(
        (
            slot
            for slot in state.slots
            if slot.phase == SaturnMidi68KR25SlotPhase.HELD
            and slot.channel == channel
            and slot.note == note
        ),
        None,
    )
    telemetry = replace(
        state.telemetry,
        note_off_count=state.telemetry.note_off_count + 1,
    )
    if selected is None:
        return replace(state, telemetry=telemetry)

    slots = list(state.slots)
    slots[selected.index] = replace(
        selected,
        phase=SaturnMidi68KR25SlotPhase.RELEASING,
        velocity=0,
        release_started_us=now_us,
        release_deadline_us=now_us + release_us,
    )
    telemetry = replace(
        telemetry,
        release_started_count=telemetry.release_started_count + 1,
    )
    return _update_peaks(replace(state, slots=tuple(slots), telemetry=telemetry))


def trace_saturn_midi_68k_r25_release_lifecycle(
    program: SaturnMidiProgram,
    *,
    release_us: int = SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
    owned_slots: int = SATURN_MIDI_68K_R25_OWNED_SLOTS,
) -> tuple[SaturnMidi68KR25ReleaseState, ...]:
    state = build_saturn_midi_68k_r25_release_state(owned_slots=owned_slots)
    trace = [state]
    for record in program.records:
        if record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 != 0:
            state = note_on_saturn_midi_68k_r25_release(
                state,
                now_us=record.time_us,
                channel=record.channel,
                note=record.data0,
                velocity=record.data1,
            )
        elif record.opcode == SaturnMidiOpcode.NOTE_OFF or (
            record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 == 0
        ):
            state = note_off_saturn_midi_68k_r25_release(
                state,
                now_us=record.time_us,
                channel=record.channel,
                note=record.data0,
                release_us=release_us,
            )
        else:
            state = advance_saturn_midi_68k_r25_releases(state, record.time_us)
        trace.append(state)
    state = advance_saturn_midi_68k_r25_releases(
        state,
        max(program.duration_us, state.now_us) + release_us,
    )
    trace.append(state)
    return tuple(trace)

