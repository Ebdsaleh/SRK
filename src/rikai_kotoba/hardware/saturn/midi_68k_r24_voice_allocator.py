"""R24 deterministic two-voice SCSP allocation reference model.

The selected CC0 reference song reaches exactly two simultaneous notes at four
points.  R24 therefore owns SCSP slots 0 and 1, takes the lowest free slot, and
does not steal voices.  This is enough to play the complete first real MIDI
file faithfully while keeping the first polyphonic hardware step small and
auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .midi_68k_r24_pitch import midi_note_to_calibrated_scsp_pitch
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    SATURN_MIDI_68K_SCSP_SLOT_COUNT,
    midi_velocity_to_scsp_mixer,
)
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram


SATURN_MIDI_68K_R24_OWNED_SLOTS = 2
SATURN_MIDI_68K_R24_FIRST_SLOT = 0
SATURN_MIDI_68K_R24_LAST_SLOT = 1
SATURN_MIDI_68K_R24_VOICE_ERROR_NONE = 0
SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY = 1
SATURN_MIDI_68K_R24_VOICE_ERROR_RANGE = 2


class SaturnMidi68KR24VoiceAllocatorError(RuntimeError):
    """Raised when the R24 two-slot allocator contract is invalid."""


@dataclass(frozen=True)
class SaturnMidi68KR24VoiceSlot:
    slot: int
    active: bool
    channel: int
    note: int
    velocity: int
    generation: int
    pitch: int
    mixer: int
    control: int


@dataclass(frozen=True)
class SaturnMidi68KR24VoiceState:
    slots: tuple[SaturnMidi68KR24VoiceSlot, ...]
    generation: int
    key_on_count: int
    key_off_count: int
    busy_count: int
    last_error: int
    peak_active: int

    @property
    def active_count(self) -> int:
        return sum(1 for slot in self.slots if slot.active)

    @property
    def owned_slots(self) -> tuple[SaturnMidi68KR24VoiceSlot, ...]:
        return self.slots[:SATURN_MIDI_68K_R24_OWNED_SLOTS]


@dataclass(frozen=True)
class SaturnMidi68KR24ProgramVoiceTrace:
    final_state: SaturnMidi68KR24VoiceState
    note_on_records: int
    note_off_records: int
    peak_active: int


def _inactive_slot(slot: int) -> SaturnMidi68KR24VoiceSlot:
    return SaturnMidi68KR24VoiceSlot(
        slot=slot,
        active=False,
        channel=0xFFFF,
        note=0xFFFF,
        velocity=0,
        generation=0,
        pitch=0,
        mixer=0,
        control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
    )


def default_saturn_midi_68k_r24_voice_state() -> SaturnMidi68KR24VoiceState:
    if SATURN_MIDI_68K_R24_OWNED_SLOTS != 2:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 first-song allocator must own exactly two slots")
    if SATURN_MIDI_68K_R24_LAST_SLOT >= SATURN_MIDI_68K_SCSP_SLOT_COUNT:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 owned slot escapes SCSP geometry")
    return SaturnMidi68KR24VoiceState(
        slots=tuple(_inactive_slot(slot) for slot in range(SATURN_MIDI_68K_SCSP_SLOT_COUNT)),
        generation=0,
        key_on_count=0,
        key_off_count=0,
        busy_count=0,
        last_error=SATURN_MIDI_68K_R24_VOICE_ERROR_NONE,
        peak_active=0,
    )


def _next_generation(value: int) -> int:
    result = (value + 1) & 0xFFFF
    return result if result else 1


def _replace_slot(
    state: SaturnMidi68KR24VoiceState,
    slot_index: int,
    new_slot: SaturnMidi68KR24VoiceSlot,
    *,
    generation: int | None = None,
    key_on_delta: int = 0,
    key_off_delta: int = 0,
    busy_delta: int = 0,
    last_error: int = SATURN_MIDI_68K_R24_VOICE_ERROR_NONE,
) -> SaturnMidi68KR24VoiceState:
    slots = list(state.slots)
    slots[slot_index] = new_slot
    active_count = sum(1 for slot in slots if slot.active)
    return SaturnMidi68KR24VoiceState(
        slots=tuple(slots),
        generation=state.generation if generation is None else generation,
        key_on_count=state.key_on_count + key_on_delta,
        key_off_count=state.key_off_count + key_off_delta,
        busy_count=state.busy_count + busy_delta,
        last_error=last_error,
        peak_active=max(state.peak_active, active_count),
    )


def note_on_saturn_midi_68k_r24_voice(
    state: SaturnMidi68KR24VoiceState,
    channel: int,
    note: int,
    velocity: int,
    *,
    pan: int = 64,
) -> SaturnMidi68KR24VoiceState:
    """Retrigger the same key or allocate the lowest free owned slot."""

    if channel < 0 or channel > 15 or note < 0 or note > 127 or velocity < 0 or velocity > 127:
        return replace(state, last_error=SATURN_MIDI_68K_R24_VOICE_ERROR_RANGE)
    if velocity == 0:
        return note_off_saturn_midi_68k_r24_voice(state, channel, note)

    target: SaturnMidi68KR24VoiceSlot | None = None
    for slot in state.owned_slots:
        if slot.active and slot.channel == channel and slot.note == note:
            target = slot
            break
    if target is None:
        for slot in state.owned_slots:
            if not slot.active:
                target = slot
                break

    if target is None:
        return SaturnMidi68KR24VoiceState(
            slots=state.slots,
            generation=state.generation,
            key_on_count=state.key_on_count,
            key_off_count=state.key_off_count,
            busy_count=state.busy_count + 1,
            last_error=SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY,
            peak_active=state.peak_active,
        )

    generation = _next_generation(state.generation)
    new_slot = replace(
        target,
        active=True,
        channel=channel,
        note=note,
        velocity=velocity,
        generation=generation,
        pitch=midi_note_to_calibrated_scsp_pitch(note),
        mixer=midi_velocity_to_scsp_mixer(velocity, pan=pan),
        control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP | SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    )
    return _replace_slot(
        state,
        target.slot,
        new_slot,
        generation=generation,
        key_on_delta=1,
    )


def note_off_saturn_midi_68k_r24_voice(
    state: SaturnMidi68KR24VoiceState,
    channel: int,
    note: int,
) -> SaturnMidi68KR24VoiceState:
    if channel < 0 or channel > 15 or note < 0 or note > 127:
        return replace(state, last_error=SATURN_MIDI_68K_R24_VOICE_ERROR_RANGE)

    for slot in state.owned_slots:
        if slot.active and slot.channel == channel and slot.note == note:
            new_slot = replace(
                slot,
                active=False,
                velocity=0,
                mixer=0,
                control=SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP,
            )
            return _replace_slot(state, slot.slot, new_slot, key_off_delta=1)
    return state


def trace_saturn_midi_68k_r24_program_voices(
    program: SaturnMidiProgram,
) -> SaturnMidi68KR24ProgramVoiceTrace:
    """Run only Note On/Off allocation semantics across one complete SRKM program."""

    state = default_saturn_midi_68k_r24_voice_state()
    note_on_records = 0
    note_off_records = 0

    for record in program.records:
        if record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 != 0:
            note_on_records += 1
            state = note_on_saturn_midi_68k_r24_voice(
                state,
                record.channel,
                record.data0,
                record.data1,
            )
        elif record.opcode == SaturnMidiOpcode.NOTE_OFF or (
            record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 == 0
        ):
            note_off_records += 1
            state = note_off_saturn_midi_68k_r24_voice(
                state,
                record.channel,
                record.data0,
            )

    return SaturnMidi68KR24ProgramVoiceTrace(
        final_state=state,
        note_on_records=note_on_records,
        note_off_records=note_off_records,
        peak_active=state.peak_active,
    )


def validate_saturn_midi_68k_r24_reference_voice_trace(
    trace: SaturnMidi68KR24ProgramVoiceTrace,
) -> None:
    """Lock the two-slot policy against the selected complete real song."""

    state = trace.final_state
    if trace.note_on_records != 140 or trace.note_off_records != 140:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 reference note-event counts changed")
    if trace.peak_active != 2 or state.peak_active != 2:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 reference no longer requires exactly two voices")
    if state.active_count != 0:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 reference leaves a physical voice active")
    if state.key_on_count != 140 or state.key_off_count != 140:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 voice key-on/off totals changed")
    if state.busy_count != 0 or state.last_error != SATURN_MIDI_68K_R24_VOICE_ERROR_NONE:
        raise SaturnMidi68KR24VoiceAllocatorError("R24 two-slot allocator cannot play the reference song")
    for slot in state.owned_slots:
        if slot.active or slot.mixer != 0 or slot.control != SATURN_MIDI_68K_SCSP_CONTROL_NORMAL_LOOP:
            raise SaturnMidi68KR24VoiceAllocatorError("R24 owned slot did not finish keyed off")


# Retained here because the resident image will reuse the physically accepted
# R23 direct-PCM source address/loop geometry for both owned slots.
SATURN_MIDI_68K_R24_SAMPLE_ADDRESS = SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS
SATURN_MIDI_68K_R24_SAMPLE_LOOP_END = SATURN_MIDI_68K_AUDIO_SAMPLE_LOOP_END
