"""Fresh full-build gate for the R23 MIDI-driven SCSP physical candidate."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .midi_68k_resident_audio_candidate_prepare import (
    SaturnMidi68KResidentAudioCandidatePrepared,
    prepare_midi_68k_resident_audio_physical_candidate,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioPhysicalCandidateFullBuildGateResult:
    prepared: SaturnMidi68KResidentAudioCandidatePrepared
    build: SaturnStandaloneBuildResult


def run_midi_68k_resident_audio_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentAudioPhysicalCandidateFullBuildGateResult:
    """Derive the fresh R23 candidate off-card and run the normal Saturn build."""

    prepared = prepare_midi_68k_resident_audio_physical_candidate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentAudioPhysicalCandidateFullBuildGateResult(
        prepared=prepared,
        build=build,
    )
