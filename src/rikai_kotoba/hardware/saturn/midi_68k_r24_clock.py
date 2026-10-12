"""R24 monotonic playback-clock contract.

R22/R23 intentionally used producer-published synthetic microsecond milestones.
That was ideal for deterministic scheduler proofs but is not a real-song clock.
R24 separates the music engine from the physical time source and models the
Saturn SH-2 free-running timer (FRT) as a wrap-extended monotonic counter.

The host model does not hard-code one Saturn CPU frequency.  A physical backend
must provide a reviewed calibration for the active hardware/video clock mode.
The FRT /128 mode gives a wrap period of roughly 0.3 seconds on Saturn, so a
normal once-per-frame producer poll is comfortably inside the one-wrap limit.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


SATURN_MIDI_68K_R24_FRT_COUNTER_BITS = 16
SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS = 1 << SATURN_MIDI_68K_R24_FRT_COUNTER_BITS
SATURN_MIDI_68K_R24_FRT_DIVIDER = 128
SATURN_MIDI_68K_R24_CLOCK_MICROSECONDS_PER_SECOND = 1_000_000

# SH-2 on-chip peripheral addresses.  R24 source/model records them so the later
# physical backend can be audited against the SH7604 FRT register map.
SATURN_MIDI_68K_R24_SH2_TIER_ADDRESS = 0xFFFFFE10
SATURN_MIDI_68K_R24_SH2_FTCSR_ADDRESS = 0xFFFFFE11
SATURN_MIDI_68K_R24_SH2_FRC_H_ADDRESS = 0xFFFFFE12
SATURN_MIDI_68K_R24_SH2_FRC_L_ADDRESS = 0xFFFFFE13
SATURN_MIDI_68K_R24_SH2_TCR_ADDRESS = 0xFFFFFE16
SATURN_MIDI_68K_R24_SH2_TOCR_ADDRESS = 0xFFFFFE17
SATURN_MIDI_68K_R24_SH2_TCR_DIV128 = 0x02


class SaturnMidi68KR24ClockError(RuntimeError):
    """Raised when a physical-clock sample violates the R24 timing contract."""


@dataclass(frozen=True)
class SaturnMidi68KR24ClockCalibration:
    """Exact rational SH-2 source frequency used by the FRT divider."""

    source_hz_numerator: int
    source_hz_denominator: int = 1
    divider: int = SATURN_MIDI_68K_R24_FRT_DIVIDER

    def validate(self) -> None:
        if self.source_hz_numerator <= 0 or self.source_hz_denominator <= 0:
            raise SaturnMidi68KR24ClockError("R24 clock frequency must be positive")
        if self.divider <= 0:
            raise SaturnMidi68KR24ClockError("R24 FRT divider must be positive")

    @property
    def tick_hz(self) -> Fraction:
        self.validate()
        return Fraction(
            self.source_hz_numerator,
            self.source_hz_denominator * self.divider,
        )

    @property
    def wrap_period_us(self) -> Fraction:
        return Fraction(
            SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS
            * SATURN_MIDI_68K_R24_CLOCK_MICROSECONDS_PER_SECOND,
            1,
        ) / self.tick_hz


@dataclass(frozen=True)
class SaturnMidi68KR24FRTClockState:
    initialized: bool = False
    last_counter: int = 0
    extended_ticks: int = 0
    origin_ticks: int = 0
    elapsed_us: int = 0
    sample_count: int = 0


def r24_frt_ticks_to_microseconds(
    ticks: int,
    calibration: SaturnMidi68KR24ClockCalibration,
) -> int:
    if ticks < 0:
        raise SaturnMidi68KR24ClockError("R24 FRT ticks must not be negative")
    calibration.validate()
    numerator = (
        ticks
        * SATURN_MIDI_68K_R24_CLOCK_MICROSECONDS_PER_SECOND
        * calibration.divider
        * calibration.source_hz_denominator
    )
    return numerator // calibration.source_hz_numerator


def sample_saturn_midi_68k_r24_frt_clock(
    state: SaturnMidi68KR24FRTClockState,
    counter: int,
    calibration: SaturnMidi68KR24ClockCalibration,
) -> SaturnMidi68KR24FRTClockState:
    """Extend one 16-bit FRT sample and return monotonic elapsed microseconds.

    The caller must sample more frequently than one FRT wrap period.  This is a
    deliberate physical-backend invariant; the host model cannot infer two or
    more unseen wraps from a 16-bit counter alone.
    """

    if counter < 0 or counter >= SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS:
        raise SaturnMidi68KR24ClockError("R24 FRT counter sample is outside 16-bit range")
    calibration.validate()

    if not state.initialized:
        return SaturnMidi68KR24FRTClockState(
            initialized=True,
            last_counter=counter,
            extended_ticks=counter,
            origin_ticks=counter,
            elapsed_us=0,
            sample_count=1,
        )

    if counter >= state.last_counter:
        delta = counter - state.last_counter
    else:
        delta = (
            SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS
            - state.last_counter
            + counter
        )

    extended = state.extended_ticks + delta
    elapsed_ticks = extended - state.origin_ticks
    elapsed_us = r24_frt_ticks_to_microseconds(elapsed_ticks, calibration)
    if elapsed_us < state.elapsed_us:
        raise SaturnMidi68KR24ClockError("R24 FRT extension moved backwards in time")

    return SaturnMidi68KR24FRTClockState(
        initialized=True,
        last_counter=counter,
        extended_ticks=extended,
        origin_ticks=state.origin_ticks,
        elapsed_us=elapsed_us,
        sample_count=state.sample_count + 1,
    )


def validate_saturn_midi_68k_r24_clock_contract() -> None:
    """Lock register geometry and prove wrap extension over a representative clock."""

    if (
        SATURN_MIDI_68K_R24_SH2_TIER_ADDRESS,
        SATURN_MIDI_68K_R24_SH2_FTCSR_ADDRESS,
        SATURN_MIDI_68K_R24_SH2_FRC_H_ADDRESS,
        SATURN_MIDI_68K_R24_SH2_FRC_L_ADDRESS,
        SATURN_MIDI_68K_R24_SH2_TCR_ADDRESS,
        SATURN_MIDI_68K_R24_SH2_TOCR_ADDRESS,
    ) != (
        0xFFFFFE10,
        0xFFFFFE11,
        0xFFFFFE12,
        0xFFFFFE13,
        0xFFFFFE16,
        0xFFFFFE17,
    ):
        raise SaturnMidi68KR24ClockError("R24 SH-2 FRT register map changed")

    # Representative 26.8741 MHz source solely exercises the host arithmetic;
    # physical code must resolve/calibrate the active Saturn clock mode.
    calibration = SaturnMidi68KR24ClockCalibration(26_874_100)
    state = sample_saturn_midi_68k_r24_frt_clock(
        SaturnMidi68KR24FRTClockState(),
        0xFFF0,
        calibration,
    )
    state = sample_saturn_midi_68k_r24_frt_clock(state, 0x0010, calibration)
    if state.extended_ticks - state.origin_ticks != 0x20:
        raise SaturnMidi68KR24ClockError("R24 FRT wrap extension changed")
    if state.elapsed_us <= 0:
        raise SaturnMidi68KR24ClockError("R24 FRT elapsed time did not advance")
