"""R27 fidelity-pass synthetic GM-family and percussion bank.

R26 physically proved complete multi-channel transport on real Saturn hardware,
but its intentionally crude eight-family bring-up bank sounded poor. R27 keeps
transport untouched and improves only source selection/mixing fidelity:

* sixteen GM eight-program families instead of eight sixteen-program buckets;
* four distinct percussion classes for the exact Space Spectre drum notes;
* a separate 128-entry SCSP pan table;
* a host reference mixer policy combining velocity, volume, expression and pan.

These are still copyright-clean generated waveforms, not General MIDI sample
fidelity or a soundfont.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .midi_68k_voice_allocator import (
    midi_pan_to_scsp_pan,
    midi_velocity_to_scsp_mixer,
)

SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS = 0x00002800
SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES = 0x0100
SATURN_MIDI_68K_R27_TIMBRE_LOOP_END = 100
SATURN_MIDI_68K_R27_GM_FAMILY_COUNT = 16

SATURN_MIDI_68K_R27_DRUM_KICK = 16
SATURN_MIDI_68K_R27_DRUM_SNARE = 17
SATURN_MIDI_68K_R27_DRUM_HIHAT = 18
SATURN_MIDI_68K_R27_DRUM_CYMBAL = 19
SATURN_MIDI_68K_R27_TIMBRE_COUNT = 20

SATURN_MIDI_68K_R27_TIMBRE_NAMES = (
    "piano",
    "chromatic",
    "organ",
    "guitar",
    "bass",
    "strings",
    "ensemble",
    "brass",
    "reed",
    "pipe",
    "synth_lead",
    "synth_pad",
    "synth_fx",
    "ethnic",
    "percussive",
    "sfx",
    "kick",
    "snare",
    "hihat",
    "cymbal",
)

SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS = (
    SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS
    + SATURN_MIDI_68K_R27_TIMBRE_COUNT * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
)
SATURN_MIDI_68K_R27_PAN_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS = (
    SATURN_MIDI_68K_R27_PAN_TABLE_ADDRESS + SATURN_MIDI_68K_R27_PAN_TABLE_BYTES
)
SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS = (
    SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_ADDRESS
    + SATURN_MIDI_68K_R27_PROGRAM_SOURCE_TABLE_BYTES
)
SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_BYTES = 128 * 2
SATURN_MIDI_68K_R27_AUDIO_DATA_END = (
    SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_ADDRESS
    + SATURN_MIDI_68K_R27_PERCUSSION_SOURCE_TABLE_BYTES
)

SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL = 9
SATURN_MIDI_68K_R27_PERCUSSION_MAP = {
    35: SATURN_MIDI_68K_R27_DRUM_KICK,
    40: SATURN_MIDI_68K_R27_DRUM_SNARE,
    42: SATURN_MIDI_68K_R27_DRUM_HIHAT,
    51: SATURN_MIDI_68K_R27_DRUM_CYMBAL,
}
SATURN_MIDI_68K_R27_PERCUSSION_FALLBACK = SATURN_MIDI_68K_R27_DRUM_SNARE


class SaturnMidi68KR27FidelityBankError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaturnMidi68KR27Timbre:
    index: int
    name: str
    address: int
    words: tuple[int, ...]


def _u16(value: int) -> int:
    value = max(-32768, min(32767, value))
    return value & 0xFFFF


def _periodic(partials: tuple[tuple[int, float], ...], *, gain: float = 12000.0) -> tuple[int, ...]:
    raw: list[float] = []
    for i in range(SATURN_MIDI_68K_R27_TIMBRE_LOOP_END):
        phase = (2.0 * math.pi * i) / SATURN_MIDI_68K_R27_TIMBRE_LOOP_END
        raw.append(sum(amplitude * math.sin(phase * harmonic) for harmonic, amplitude in partials))
    peak = max(abs(value) for value in raw) or 1.0
    scale = gain / peak
    words = [_u16(int(round(value * scale))) for value in raw]
    words.append(words[0])
    return tuple(words)


_GM_PARTIALS: tuple[tuple[tuple[int, float], ...], ...] = (
    ((1, 1.00), (2, 0.32), (3, 0.12), (4, 0.06)),
    ((1, 1.00), (3, 0.42), (5, 0.12)),
    ((1, 1.00), (2, 0.45), (4, 0.22), (6, 0.10)),
    ((1, 1.00), (2, 0.28), (3, 0.22), (5, 0.08)),
    ((1, 1.00), (2, 0.18), (3, 0.07)),
    ((1, 1.00), (2, 0.30), (3, 0.22), (4, 0.13)),
    ((1, 1.00), (2, 0.22), (3, 0.16), (5, 0.10)),
    ((1, 1.00), (2, 0.48), (3, 0.26), (4, 0.10)),
    ((1, 1.00), (3, 0.38), (5, 0.18)),
    ((1, 1.00), (2, 0.08), (3, 0.03)),
    ((1, 1.00), (2, 0.40), (4, 0.24), (7, 0.10)),
    ((1, 1.00), (2, 0.16), (3, 0.10), (5, 0.05)),
    ((1, 1.00), (5, 0.30), (7, 0.18)),
    ((1, 1.00), (3, 0.30), (6, 0.10)),
    ((1, 1.00), (4, 0.34), (7, 0.20)),
    ((1, 1.00), (3, 0.50), (5, 0.28), (7, 0.16)),
)


def _noise_wave(kind: int) -> tuple[int, ...]:
    lfsr = 0xACE1
    values: list[int] = []
    for i in range(SATURN_MIDI_68K_R27_TIMBRE_LOOP_END):
        bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
        lfsr = (lfsr >> 1) | (bit << 15)
        noise = 1.0 if (lfsr & 1) else -1.0
        phase = (2.0 * math.pi * i) / SATURN_MIDI_68K_R27_TIMBRE_LOOP_END
        if kind == SATURN_MIDI_68K_R27_DRUM_KICK:
            sample = 0.90 * math.sin(phase) + 0.18 * math.sin(phase * 2.0)
        elif kind == SATURN_MIDI_68K_R27_DRUM_SNARE:
            sample = 0.62 * noise + 0.38 * math.sin(phase * 3.0)
        elif kind == SATURN_MIDI_68K_R27_DRUM_HIHAT:
            carrier = 1.0 if (i & 1) else -1.0
            sample = 0.55 * noise + 0.45 * carrier
        elif kind == SATURN_MIDI_68K_R27_DRUM_CYMBAL:
            sample = (
                0.34 * noise
                + 0.28 * math.sin(phase * 7.0)
                + 0.22 * math.sin(phase * 11.0)
                + 0.16 * math.sin(phase * 13.0)
            )
        else:
            raise SaturnMidi68KR27FidelityBankError("unknown R27 percussion timbre")
        values.append(_u16(int(round(sample * 10500.0))))
    values.append(values[0])
    return tuple(values)


def build_srk_saturn_midi_68k_r27_timbre_bank() -> tuple[SaturnMidi68KR27Timbre, ...]:
    result: list[SaturnMidi68KR27Timbre] = []
    for index, name in enumerate(SATURN_MIDI_68K_R27_TIMBRE_NAMES):
        if index < SATURN_MIDI_68K_R27_GM_FAMILY_COUNT:
            words = _periodic(_GM_PARTIALS[index])
        else:
            words = _noise_wave(index)
        if len(words) != SATURN_MIDI_68K_R27_TIMBRE_LOOP_END + 1:
            raise SaturnMidi68KR27FidelityBankError("R27 timbre length changed")
        result.append(
            SaturnMidi68KR27Timbre(
                index=index,
                name=name,
                address=(
                    SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS
                    + index * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
                ),
                words=words,
            )
        )
    return tuple(result)


def srk_saturn_midi_68k_r27_program_timbre(program: int) -> int:
    if program < 0 or program > 127:
        raise SaturnMidi68KR27FidelityBankError("MIDI program is outside 0..127")
    return program // 8


def srk_saturn_midi_68k_r27_channel_timbre(channel: int, program: int, note: int) -> int:
    if channel < 0 or channel > 15:
        raise SaturnMidi68KR27FidelityBankError("MIDI channel is outside 0..15")
    if note < 0 or note > 127:
        raise SaturnMidi68KR27FidelityBankError("MIDI note is outside 0..127")
    if channel == SATURN_MIDI_68K_R27_PERCUSSION_CHANNEL:
        return SATURN_MIDI_68K_R27_PERCUSSION_MAP.get(
            note, SATURN_MIDI_68K_R27_PERCUSSION_FALLBACK
        )
    return srk_saturn_midi_68k_r27_program_timbre(program)


def build_srk_saturn_midi_68k_r27_pan_table() -> tuple[int, ...]:
    return tuple((midi_pan_to_scsp_pan(pan) & 0x1F) << 8 for pan in range(128))


def build_srk_saturn_midi_68k_r27_program_source_table() -> tuple[int, ...]:
    return tuple(
        SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS
        + srk_saturn_midi_68k_r27_program_timbre(program)
        * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
        for program in range(128)
    )


def build_srk_saturn_midi_68k_r27_percussion_source_table() -> tuple[int, ...]:
    return tuple(
        SATURN_MIDI_68K_R27_TIMBRE_BANK_ADDRESS
        + SATURN_MIDI_68K_R27_PERCUSSION_MAP.get(
            note, SATURN_MIDI_68K_R27_PERCUSSION_FALLBACK
        )
        * SATURN_MIDI_68K_R27_TIMBRE_STRIDE_BYTES
        for note in range(128)
    )


def _level_bits(value: int) -> int:
    if value < 0 or value > 127:
        raise SaturnMidi68KR27FidelityBankError("MIDI gain value is outside 0..127")
    return midi_velocity_to_scsp_mixer(value, pan=64) & 0xE000


def srk_saturn_midi_68k_r27_mixer_word(
    velocity: int,
    *,
    volume: int,
    expression: int,
    pan: int,
) -> int:
    if pan < 0 or pan > 127:
        raise SaturnMidi68KR27FidelityBankError("MIDI pan is outside 0..127")
    level = min(_level_bits(velocity), _level_bits(volume), _level_bits(expression))
    return level | build_srk_saturn_midi_68k_r27_pan_table()[pan]
