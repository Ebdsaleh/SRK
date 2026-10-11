"""Reserved module for the resident-decoder physical candidate full-build gate.

The reviewed seven-record physical binding is developed and regression-locked
separately.  Candidate derivation is intentionally not exposed from this module
until its own full-build tranche is complete.
"""

from __future__ import annotations


class SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised if an incomplete physical-candidate build path is invoked."""


def prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate(*args, **kwargs):
    raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
        "resident-decoder physical candidate full-build gate is not enabled in this source tranche"
    )


def run_midi_68k_resident_decoder_physical_candidate_full_build_gate(*args, **kwargs):
    raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
        "resident-decoder physical candidate full-build gate is not enabled in this source tranche"
    )
