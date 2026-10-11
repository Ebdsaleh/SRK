"""Fresh off-card full-build gate for the resident stream/scheduler physical proof."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .midi_68k_resident_stream_candidate_prepare import (
    SaturnMidi68KResidentStreamCandidatePrepared,
    SaturnMidi68KResidentStreamCandidatePrepareError,
    prepare_midi_68k_resident_stream_physical_candidate,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentStreamPhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the fresh stream/scheduler physical candidate cannot be derived."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamPhysicalCandidateFullBuildGateResult:
    prepared: SaturnMidi68KResidentStreamCandidatePrepared
    build: SaturnStandaloneBuildResult


def run_midi_68k_resident_stream_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStreamPhysicalCandidateFullBuildGateResult:
    try:
        prepared = prepare_midi_68k_resident_stream_physical_candidate(
            baseline_project,
            output_directory,
            **kwargs,
        )
    except SaturnMidi68KResidentStreamCandidatePrepareError as exc:
        raise SaturnMidi68KResidentStreamPhysicalCandidateFullBuildGateError(
            str(exc)
        ) from exc
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentStreamPhysicalCandidateFullBuildGateResult(
        prepared=prepared,
        build=build,
    )
