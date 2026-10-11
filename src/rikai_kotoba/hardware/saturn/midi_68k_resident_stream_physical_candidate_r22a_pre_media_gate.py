"""Independent read-only pre-media wrapper for the corrected R22A candidate."""

from __future__ import annotations

import os

from . import midi_68k_resident_stream_physical_candidate_pre_media_gate as _base
from .midi_68k_resident_stream_physical_candidate_r22a import (
    render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
)


SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaResult = (
    _base.SaturnMidi68KResidentStreamPhysicalCandidatePreMediaResult
)


class SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaGateError(RuntimeError):
    """Raised when the corrected R22A candidate fails independent media review."""


def inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaResult:
    """Run the accepted R22 verifier against the corrected R22A proof renderer."""

    original_renderer = _base.render_srk_saturn_midi_68k_stream_physical_proof_source
    _base.render_srk_saturn_midi_68k_stream_physical_proof_source = (
        render_srk_saturn_midi_68k_stream_physical_proof_source_r22a
    )
    try:
        try:
            return _base.inspect_midi_68k_resident_stream_physical_candidate_pre_media(
                project_directory,
                card_root,
                **kwargs,
            )
        except _base.SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError as exc:
            raise SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaGateError(
                str(exc)
            ) from exc
    finally:
        _base.render_srk_saturn_midi_68k_stream_physical_proof_source = original_renderer
