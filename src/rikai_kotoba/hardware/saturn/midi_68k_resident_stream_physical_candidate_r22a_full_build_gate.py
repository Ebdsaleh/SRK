"""Fresh full-build gate for the R22A physical-proof instrumentation correction."""

from __future__ import annotations

from dataclasses import dataclass
import os

from . import midi_68k_resident_stream_candidate_prepare as _prepare
from .midi_68k_resident_stream_candidate_prepare import (
    SaturnMidi68KResidentStreamCandidatePrepared,
    SaturnMidi68KResidentStreamCandidatePrepareError,
)
from .midi_68k_resident_stream_physical_candidate_r22a import (
    render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateError(RuntimeError):
    """Raised when a fresh corrected R22A candidate cannot be derived."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateResult:
    prepared: SaturnMidi68KResidentStreamCandidatePrepared
    build: SaturnStandaloneBuildResult


def run_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateResult:
    """Derive R22A from the accepted inert baseline and run the normal build."""

    original_renderer = _prepare.render_srk_saturn_midi_68k_stream_physical_proof_source
    _prepare.render_srk_saturn_midi_68k_stream_physical_proof_source = (
        render_srk_saturn_midi_68k_stream_physical_proof_source_r22a
    )
    try:
        try:
            prepared = _prepare.prepare_midi_68k_resident_stream_physical_candidate(
                baseline_project,
                output_directory,
                **kwargs,
            )
        except SaturnMidi68KResidentStreamCandidatePrepareError as exc:
            raise SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateError(
                str(exc)
            ) from exc
    finally:
        _prepare.render_srk_saturn_midi_68k_stream_physical_proof_source = original_renderer

    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateResult(
        prepared=prepared,
        build=build,
    )
