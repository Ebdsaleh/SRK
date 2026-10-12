"""SCSP RR calibration-matrix contract for R25 physical measurement."""

from __future__ import annotations

from dataclasses import dataclass

from .midi_68k_r25_envelope import (
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
    build_saturn_midi_68k_r25_envelope_plan,
)


class SaturnMidi68KR25RRCalibrationError(RuntimeError):
    """Raised when measured RR evidence cannot select a deterministic policy."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationEntry:
    release_rate: int
    eg1_word: int
    eg2_word: int
    measured_release_us: int | None


@dataclass(frozen=True)
class SaturnMidi68KR25RRSelection:
    release_rate: int
    measured_release_us: int
    target_release_us: int
    absolute_error_us: int


def build_saturn_midi_68k_r25_rr_calibration_matrix(
    measured_release_us: dict[int, int] | None = None,
) -> tuple[SaturnMidi68KR25RRCalibrationEntry, ...]:
    measured = measured_release_us or {}
    if any(rate < 0 or rate > 31 for rate in measured):
        raise SaturnMidi68KR25RRCalibrationError("measured RR key must be within 0..31")
    if any(duration <= 0 for duration in measured.values()):
        raise SaturnMidi68KR25RRCalibrationError("measured release must be positive")
    entries = []
    for release_rate in range(32):
        plan = build_saturn_midi_68k_r25_envelope_plan(release_rate=release_rate)
        entries.append(
            SaturnMidi68KR25RRCalibrationEntry(
                release_rate=release_rate,
                eg1_word=plan.eg1_word,
                eg2_word=plan.eg2_word,
                measured_release_us=measured.get(release_rate),
            )
        )
    return tuple(entries)


def select_saturn_midi_68k_r25_rr(
    entries: tuple[SaturnMidi68KR25RRCalibrationEntry, ...],
    *,
    target_release_us: int = SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
) -> SaturnMidi68KR25RRSelection:
    if target_release_us <= 0:
        raise SaturnMidi68KR25RRCalibrationError("target release must be positive")
    measured = tuple(entry for entry in entries if entry.measured_release_us is not None)
    if not measured:
        raise SaturnMidi68KR25RRCalibrationError(
            "physical RR measurements are required before selecting release policy"
        )
    chosen = min(
        measured,
        key=lambda entry: (
            abs(int(entry.measured_release_us) - target_release_us),
            entry.release_rate,
        ),
    )
    duration = int(chosen.measured_release_us)
    return SaturnMidi68KR25RRSelection(
        release_rate=chosen.release_rate,
        measured_release_us=duration,
        target_release_us=target_release_us,
        absolute_error_us=abs(duration - target_release_us),
    )

