"""R25 SCSP envelope/register model for non-abrupt MIDI Note Off.

The physically accepted R24 service issues KEY_OFF and then immediately writes
zero to the slot mixer.  That deterministic hard mute made the first real-song
proof easy to verify, but it prevents the SCSP envelope generator from producing
an audible release segment.

R25 models the documented SCSP EG fields without guessing a hardware release
rate.  The eventual physical calibration tranche must select RR explicitly and
measure it before the value becomes an accepted musical policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
)


SATURN_MIDI_68K_R25_ATTACK_RATE = 0x1F
SATURN_MIDI_68K_R25_DECAY1_RATE = 0x00
SATURN_MIDI_68K_R25_DECAY2_RATE = 0x00
SATURN_MIDI_68K_R25_DECAY_LEVEL = 0x00
SATURN_MIDI_68K_R25_KEY_RATE_SCALING_OFF = 0x0F


class SaturnMidi68KR25EnvelopeError(RuntimeError):
    """Raised when an R25 SCSP envelope field is outside hardware range."""


@dataclass(frozen=True)
class SaturnMidi68KR25EnvelopePlan:
    attack_rate: int
    decay1_rate: int
    decay2_rate: int
    eg_hold: bool
    loop_start_link: bool
    key_rate_scaling: int
    decay_level: int
    release_rate: int
    target_release_us: int
    owned_slots: int
    hard_mixer_zero_on_note_off: bool

    @property
    def eg1_word(self) -> int:
        return pack_saturn_midi_68k_r25_eg1(
            d2r=self.decay2_rate,
            d1r=self.decay1_rate,
            eg_hold=self.eg_hold,
            ar=self.attack_rate,
        )

    @property
    def eg2_word(self) -> int:
        return pack_saturn_midi_68k_r25_eg2(
            loop_start_link=self.loop_start_link,
            krs=self.key_rate_scaling,
            decay_level=self.decay_level,
            release_rate=self.release_rate,
        )


def _require_bits(value: int, bits: int, label: str) -> int:
    maximum = (1 << bits) - 1
    if value < 0 or value > maximum:
        raise SaturnMidi68KR25EnvelopeError(
            f"{label} must be within 0..0x{maximum:X}: {value}"
        )
    return value


def pack_saturn_midi_68k_r25_eg1(
    *,
    d2r: int,
    d1r: int,
    eg_hold: bool,
    ar: int,
) -> int:
    """Pack SCSP slot +08h: D2R[4:0], D1R[4:0], EGHOLD, AR[4:0]."""

    return (
        (_require_bits(d2r, 5, "D2R") << 11)
        | (_require_bits(d1r, 5, "D1R") << 6)
        | ((1 if eg_hold else 0) << 5)
        | _require_bits(ar, 5, "AR")
    )


def pack_saturn_midi_68k_r25_eg2(
    *,
    loop_start_link: bool,
    krs: int,
    decay_level: int,
    release_rate: int,
) -> int:
    """Pack SCSP slot +0Ah: LPSLNK, KRS[3:0], DL[4:0], RR[4:0]."""

    return (
        ((1 if loop_start_link else 0) << 14)
        | (_require_bits(krs, 4, "KRS") << 10)
        | (_require_bits(decay_level, 5, "DL") << 5)
        | _require_bits(release_rate, 5, "RR")
    )


def build_saturn_midi_68k_r25_envelope_plan(
    *,
    release_rate: int,
    target_release_us: int = SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
) -> SaturnMidi68KR25EnvelopePlan:
    """Build the candidate sustain/release shape around one explicit RR value.

    RR is deliberately a required argument.  The source/model gate validates the
    register semantics, but the physical calibration gate must determine which RR
    best matches the target release time on Saturn hardware.
    """

    _require_bits(release_rate, 5, "RR")
    if target_release_us <= 0:
        raise SaturnMidi68KR25EnvelopeError("target_release_us must be positive")
    return SaturnMidi68KR25EnvelopePlan(
        attack_rate=SATURN_MIDI_68K_R25_ATTACK_RATE,
        decay1_rate=SATURN_MIDI_68K_R25_DECAY1_RATE,
        decay2_rate=SATURN_MIDI_68K_R25_DECAY2_RATE,
        eg_hold=False,
        loop_start_link=False,
        key_rate_scaling=SATURN_MIDI_68K_R25_KEY_RATE_SCALING_OFF,
        decay_level=SATURN_MIDI_68K_R25_DECAY_LEVEL,
        release_rate=release_rate,
        target_release_us=target_release_us,
        owned_slots=SATURN_MIDI_68K_R25_OWNED_SLOTS,
        hard_mixer_zero_on_note_off=False,
    )
