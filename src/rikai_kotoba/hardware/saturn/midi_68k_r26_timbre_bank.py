"""Deterministic R26 Saturn-native synthetic timbre bank.

This is deliberately not a claim of General MIDI sample fidelity. It provides
nine small, copyright-clean PCM loops so real GM program changes and channel-10
percussion become audibly distinct on the SCSP while SRK's real MIDI transport
is exercised end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass


SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS = 0x00002800
SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES = 0x0100
SATURN_MIDI_68K_R26_TIMBRE_LOOP_END = 100
SATURN_MIDI_68K_R26_MELODIC_TIMBRES = 8
SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE = 8
SATURN_MIDI_68K_R26_TIMBRE_COUNT = 9

SATURN_MIDI_68K_R26_TIMBRE_NAMES = (
    "soft",
    "square",
    "saw",
    "triangle",
    "pulse",
    "organ",
    "reed",
    "bright",
    "percussion",
)


class SaturnMidi68KR26TimbreBankError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaturnMidi68KR26Timbre:
    index: int
    name: str
    address: int
    words: tuple[int, ...]


def _u16(value: int) -> int:
    value = max(-32768, min(32767, value))
    return value & 0xFFFF


def _wave(kind: int) -> tuple[int, ...]:
    values: list[int] = []
    lfsr = 0xACE1
    for i in range(SATURN_MIDI_68K_R26_TIMBRE_LOOP_END):
        if kind == 0:
            quarter = (i * 4) // 100
            position = i % 25
            ramp = position * 600
            signed = ramp if quarter in (0, 3) else -ramp
        elif kind == 1:
            signed = 9000 if i < 50 else -9000
        elif kind == 2:
            signed = -10000 + (i * 20000 // 99)
        elif kind == 3:
            x = i if i < 50 else 99 - i
            signed = -9000 + (x * 18000 // 49)
        elif kind == 4:
            signed = 10500 if i < 25 else -7000
        elif kind == 5:
            fundamental = 6500 if i < 50 else -6500
            harmonic = 2800 if (i % 25) < 12 else -2800
            signed = fundamental + harmonic
        elif kind == 6:
            signed = 8000 if (i % 30) < 11 else -6500
        elif kind == 7:
            signed = (-10500 + (i * 21000 // 99)) + (
                2500 if (i % 20) < 10 else -2500
            )
        elif kind == SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE:
            bit = ((lfsr >> 0) ^ (lfsr >> 2) ^ (lfsr >> 3) ^ (lfsr >> 5)) & 1
            lfsr = (lfsr >> 1) | (bit << 15)
            signed = 11500 if (lfsr & 1) else -11500
        else:
            raise SaturnMidi68KR26TimbreBankError("unknown R26 timbre")
        values.append(_u16(signed))
    values.append(values[0])
    return tuple(values)


def build_srk_saturn_midi_68k_r26_timbre_bank() -> tuple[SaturnMidi68KR26Timbre, ...]:
    result = []
    for index, name in enumerate(SATURN_MIDI_68K_R26_TIMBRE_NAMES):
        words = _wave(index)
        if len(words) != SATURN_MIDI_68K_R26_TIMBRE_LOOP_END + 1:
            raise SaturnMidi68KR26TimbreBankError("R26 timbre length changed")
        result.append(
            SaturnMidi68KR26Timbre(
                index=index,
                name=name,
                address=SATURN_MIDI_68K_R26_TIMBRE_BANK_ADDRESS
                + index * SATURN_MIDI_68K_R26_TIMBRE_STRIDE_BYTES,
                words=words,
            )
        )
    return tuple(result)


def srk_saturn_midi_68k_r26_program_timbre(program: int) -> int:
    if program < 0 or program > 127:
        raise SaturnMidi68KR26TimbreBankError("MIDI program is outside 0..127")
    return program // 16


def srk_saturn_midi_68k_r26_channel_timbre(channel: int, program: int) -> int:
    if channel < 0 or channel > 15:
        raise SaturnMidi68KR26TimbreBankError("MIDI channel is outside 0..15")
    if channel == 9:
        return SATURN_MIDI_68K_R26_PERCUSSION_TIMBRE
    return srk_saturn_midi_68k_r26_program_timbre(program)
