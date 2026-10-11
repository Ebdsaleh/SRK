"""Fresh off-card full-build gate for the seven-record resident decoder proof."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .midi_68k_resident_decoder_candidate_baseline import (
    SaturnMidi68KResidentDecoderCandidateBaselineError,
)
from .midi_68k_resident_decoder_candidate_prepare import (
    SaturnMidi68KResidentDecoderCandidatePrepared,
    SaturnMidi68KResidentDecoderCandidatePrepareError,
    prepare_resident_decoder_physical_candidate,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the fresh physical candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateResult:
    prepared: SaturnMidi68KResidentDecoderCandidatePrepared
    build: SaturnStandaloneBuildResult


def prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentDecoderCandidatePrepared:
    """Prepare the fresh candidate tree without invoking the compiler."""

    try:
        return prepare_resident_decoder_physical_candidate(
            baseline_project,
            output_directory,
            **kwargs,
        )
    except (
        SaturnMidi68KResidentDecoderCandidateBaselineError,
        SaturnMidi68KResidentDecoderCandidatePrepareError,
    ) as exc:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(str(exc)) from exc


def run_midi_68k_resident_decoder_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateResult:
    """Prepare and build the callable off-card candidate; never deploy it."""

    prepared = prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateResult(
        prepared=prepared,
        build=build,
    )
