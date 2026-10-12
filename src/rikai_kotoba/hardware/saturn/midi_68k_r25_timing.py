"""R25 source-vs-observed event timing telemetry model."""

from __future__ import annotations

from dataclasses import dataclass


class SaturnMidi68KR25TimingError(RuntimeError):
    """Raised when timing observations are incomplete or out of order."""


@dataclass(frozen=True)
class SaturnMidi68KR25TimingObservation:
    record_index: int
    expected_us: int
    observed_us: int

    @property
    def signed_error_us(self) -> int:
        return self.observed_us - self.expected_us


@dataclass(frozen=True)
class SaturnMidi68KR25TimingAudit:
    observation_count: int
    early_count: int
    late_count: int
    exact_count: int
    maximum_early_us: int
    maximum_late_us: int
    maximum_absolute_error_us: int
    tolerance_us: int
    violation_count: int


def audit_saturn_midi_68k_r25_timing(
    observations: tuple[SaturnMidi68KR25TimingObservation, ...],
    *,
    tolerance_us: int,
) -> SaturnMidi68KR25TimingAudit:
    if tolerance_us < 0:
        raise SaturnMidi68KR25TimingError("tolerance_us must be non-negative")
    previous_index = -1
    errors: list[int] = []
    for observation in observations:
        if observation.record_index <= previous_index:
            raise SaturnMidi68KR25TimingError("record indices must be strictly increasing")
        if observation.expected_us < 0 or observation.observed_us < 0:
            raise SaturnMidi68KR25TimingError("timestamps must be non-negative")
        previous_index = observation.record_index
        errors.append(observation.signed_error_us)
    early = tuple(-error for error in errors if error < 0)
    late = tuple(error for error in errors if error > 0)
    return SaturnMidi68KR25TimingAudit(
        observation_count=len(errors),
        early_count=len(early),
        late_count=len(late),
        exact_count=sum(error == 0 for error in errors),
        maximum_early_us=max(early, default=0),
        maximum_late_us=max(late, default=0),
        maximum_absolute_error_us=max((abs(error) for error in errors), default=0),
        tolerance_us=tolerance_us,
        violation_count=sum(abs(error) > tolerance_us for error in errors),
    )

