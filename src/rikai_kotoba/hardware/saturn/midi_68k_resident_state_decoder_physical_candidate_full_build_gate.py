"""Fresh off-card full-build gate for the Phase-B full-state physical proof."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .midi_68k_resident_state_decoder_candidate_baseline import (
    SaturnMidi68KResidentStateCandidateBaselineError,
)
from .midi_68k_resident_state_decoder_candidate_prepare import (
    SaturnMidi68KResidentStateCandidatePrepared,
    SaturnMidi68KResidentStateCandidatePrepareError,
    prepare_resident_state_decoder_physical_candidate,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentStatePhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the fresh Phase-B physical candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStatePhysicalCandidateFullBuildGateResult:
    prepared: SaturnMidi68KResidentStateCandidatePrepared
    build: SaturnStandaloneBuildResult


def prepare_midi_68k_resident_state_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStateCandidatePrepared:
    try:
        return prepare_resident_state_decoder_physical_candidate(
            baseline_project,
            output_directory,
            **kwargs,
        )
    except (
        SaturnMidi68KResidentStateCandidateBaselineError,
        SaturnMidi68KResidentStateCandidatePrepareError,
    ) as exc:
        raise SaturnMidi68KResidentStatePhysicalCandidateFullBuildGateError(
            str(exc)
        ) from exc


def run_midi_68k_resident_state_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStatePhysicalCandidateFullBuildGateResult:
    prepared = prepare_midi_68k_resident_state_physical_candidate_full_build_gate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentStatePhysicalCandidateFullBuildGateResult(
        prepared=prepared,
        build=build,
    )
