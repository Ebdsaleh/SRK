"""R28 percussion-fidelity policy layered above the accepted R27 bank.

R27 improved melodic family selection and channel mixing on physical Saturn
hardware, but the reference/physical comparison showed no recognisable
percussion. The R27 percussion sources were selected by GM drum note, then the
same drum note was also fed through the melodic pitch table and every source was
treated as a continuously looping melodic oscillator.

R28 keeps the exact R27 melodic bank and replaces only the four Space Spectre
drum waveforms/pitch policy. Each drum contains a short deterministic transient
followed by a zero-valued loop tail. Normal-loop mode therefore remains on the
already exercised SCSP path: the first pass emits the hit, then LSA..LEA loops
silence until the ordinary MIDI Note Off/release lifecycle retires the slot.
"""

from __future__ import annotations

import math

from .midi_68k_r24_pitch import build_saturn_midi_68k_r24_pitch_table
from .midi_68k_r27_fidelity_bank import (
    SATURN_MIDI_68K_R27_AUDIO_DATA_END,
    SATURN_MIDI_68K_R27_DRUM_CYMBAL,
    SATURN_MIDI_68K_R27_DRUM_HIHAT,
    SATURN_MIDI_68K_R27_DRUM_KICK,
    SATURN_MIDI_68K_R27_DRUM_SNARE,
    SATURN_MIDI_68K_R27_PERCUSSION_FALLBACK,
    SATURN_MIDI_68K_R27_PERCUSSION_MAP,
    SATURN_MIDI_68K_R27_TIMBRE_LOOP_END,
    SaturnMidi68KR27Timbre,
    build_srk_saturn_midi_68k_r27_timbre_bank,
)


SATURN_MIDI_68K_R28_DRUM_LOOP_START = 96
SATURN_MIDI_68K_R28_DRUM_LOOP_END = SATURN_MIDI_68K_R27_TIMBRE_LOOP_END

# GM channel-10 note numbers select instruments. They must not also become the
# melodic pitch of the selected sample. These fixed calibrated pitch-table
# indices instead control each transient's playback rate/duration.
SATURN_MIDI_68K_R28_DRUM_PITCH_NOTE = {
    35: 45,  # kick: slower ~110-Hz playback basis
    40: 57,  # snare: half-rate noise/body
    42: 69,  # closed hat: near-unity playback to retain HF content
    51: 57,  # ride/cymbal: longer half-rate metallic burst
}
SATURN_MIDI_68K_R28_DRUM_FALLBACK_PITCH_NOTE = 57

# R27 stops at 0x3F00. The final 0x100 bytes before the unchanged resident
# program at 0x4000 hold a compact 128-word percussion-pitch table.
SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS = SATURN_MIDI_68K_R27_AUDIO_DATA_END
SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_R28_AUDIO_DATA_END = (
    SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_ADDRESS
    + SATURN_MIDI_68K_R28_PERCUSSION_PITCH_TABLE_BYTES
)

# Two otherwise unused R25/R26 global words. FIX1 owns word 23; slot records
# begin at word 32. These counters are diagnostic breadcrumbs only and do not
# participate in scheduling.
SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD = 24
SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD = 25


class SaturnMidi68KR28PercussionError(RuntimeError):
    pass


def _u16(value: float) -> int:
    signed = max(-32768, min(32767, int(round(value))))
    return signed & 0xFFFF


def _noise_sequence(count: int, seed: int) -> list[float]:
    lfsr = seed & 0xFFFF
    values: list[float] = []
    for _ in range(count):
        bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
        lfsr = (lfsr >> 1) | (bit << 15)
        values.append(1.0 if (lfsr & 1) else -1.0)
    return values


def _drum_transient(kind: int) -> tuple[int, ...]:
    active = SATURN_MIDI_68K_R28_DRUM_LOOP_START
    noise = _noise_sequence(active, 0xACE1 ^ (kind * 0x1111))
    samples: list[int] = []

    phase = 0.0
    for index in range(active):
        t = index / float(max(1, active - 1))
        env = (1.0 - t) ** 2.15

        if kind == SATURN_MIDI_68K_R27_DRUM_KICK:
            # Downward chirp. The fixed playback-rate policy stretches this into
            # a short thump instead of using GM note 35 as melodic pitch.
            cycles_per_sample = 0.030 - (0.020 * t)
            phase += 2.0 * math.pi * cycles_per_sample
            sample = math.sin(phase) * env
            gain = 23000.0
        elif kind == SATURN_MIDI_68K_R27_DRUM_SNARE:
            tone = math.sin((2.0 * math.pi * index * 7.0) / active)
            sample = (0.78 * noise[index] + 0.22 * tone) * env
            gain = 19000.0
        elif kind == SATURN_MIDI_68K_R27_DRUM_HIHAT:
            carrier = 1.0 if (index & 1) else -1.0
            sample = (0.68 * carrier + 0.32 * noise[index]) * (env ** 1.35)
            gain = 17000.0
        elif kind == SATURN_MIDI_68K_R27_DRUM_CYMBAL:
            metallic = (
                0.40 * math.sin((2.0 * math.pi * index * 11.0) / active)
                + 0.32 * math.sin((2.0 * math.pi * index * 17.0) / active)
                + 0.28 * math.sin((2.0 * math.pi * index * 23.0) / active)
            )
            sample = (0.48 * noise[index] + 0.52 * metallic) * env
            gain = 18000.0
        else:
            raise SaturnMidi68KR28PercussionError("unknown R28 drum kind")

        samples.append(_u16(sample * gain))

    # LSA points here. From this point through LEA everything is exactly zero,
    # so the already-proven NORMAL_LOOP mode becomes silent after one hit.
    samples.extend(
        [0]
        * (
            SATURN_MIDI_68K_R28_DRUM_LOOP_END
            + 1
            - SATURN_MIDI_68K_R28_DRUM_LOOP_START
        )
    )
    if len(samples) != SATURN_MIDI_68K_R28_DRUM_LOOP_END + 1:
        raise SaturnMidi68KR28PercussionError("R28 drum transient length changed")
    if any(
        samples[index] != 0
        for index in range(SATURN_MIDI_68K_R28_DRUM_LOOP_START, len(samples))
    ):
        raise SaturnMidi68KR28PercussionError("R28 silent loop tail is not zero")
    return tuple(samples)


def build_srk_saturn_midi_68k_r28_timbre_bank() -> tuple[SaturnMidi68KR27Timbre, ...]:
    """Return R27 melodic timbres plus transient R28 drums at identical addresses."""
    base = list(build_srk_saturn_midi_68k_r27_timbre_bank())
    for kind in (
        SATURN_MIDI_68K_R27_DRUM_KICK,
        SATURN_MIDI_68K_R27_DRUM_SNARE,
        SATURN_MIDI_68K_R27_DRUM_HIHAT,
        SATURN_MIDI_68K_R27_DRUM_CYMBAL,
    ):
        old = base[kind]
        base[kind] = SaturnMidi68KR27Timbre(
            index=old.index,
            name=old.name,
            address=old.address,
            words=_drum_transient(kind),
        )
    return tuple(base)


def build_srk_saturn_midi_68k_r28_percussion_pitch_table() -> tuple[int, ...]:
    calibrated = build_saturn_midi_68k_r24_pitch_table()
    result: list[int] = []
    for note in range(128):
        pitch_note = SATURN_MIDI_68K_R28_DRUM_PITCH_NOTE.get(
            note, SATURN_MIDI_68K_R28_DRUM_FALLBACK_PITCH_NOTE
        )
        result.append(calibrated[pitch_note])
    return tuple(result)


def srk_saturn_midi_68k_r28_percussion_pitch_note(note: int) -> int:
    if note < 0 or note > 127:
        raise SaturnMidi68KR28PercussionError("MIDI drum note is outside 0..127")
    return SATURN_MIDI_68K_R28_DRUM_PITCH_NOTE.get(
        note, SATURN_MIDI_68K_R28_DRUM_FALLBACK_PITCH_NOTE
    )


def validate_srk_saturn_midi_68k_r28_percussion_layout() -> None:
    if SATURN_MIDI_68K_R28_DRUM_LOOP_START <= 0:
        raise SaturnMidi68KR28PercussionError("R28 drum loop start must follow the transient")
    if SATURN_MIDI_68K_R28_DRUM_LOOP_START >= SATURN_MIDI_68K_R28_DRUM_LOOP_END:
        raise SaturnMidi68KR28PercussionError("R28 drum silent-loop range is empty")
    if SATURN_MIDI_68K_R28_AUDIO_DATA_END != 0x00004000:
        raise SaturnMidi68KR28PercussionError("R28 audio data must end exactly at 0x4000")
    if SATURN_MIDI_68K_R28_DRUM_KEY_ON_COUNT_WORD <= 23:
        raise SaturnMidi68KR28PercussionError("R28 drum telemetry overlaps FIX1 scratch")
    if SATURN_MIDI_68K_R28_LAST_DRUM_NOTE_WORD >= 32:
        raise SaturnMidi68KR28PercussionError("R28 drum telemetry overlaps slot ledger")

    table = build_srk_saturn_midi_68k_r28_percussion_pitch_table()
    if len(table) != 128:
        raise SaturnMidi68KR28PercussionError("R28 percussion pitch table size changed")

    if tuple(sorted(SATURN_MIDI_68K_R27_PERCUSSION_MAP)) != (35, 40, 42, 51):
        raise SaturnMidi68KR28PercussionError("R27 Space Spectre percussion map changed")
    if SATURN_MIDI_68K_R27_PERCUSSION_FALLBACK != SATURN_MIDI_68K_R27_DRUM_SNARE:
        raise SaturnMidi68KR28PercussionError("R27 percussion fallback changed")
