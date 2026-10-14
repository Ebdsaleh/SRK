"""Fresh off-card full-build wrapper for the R26 Space Spectre FIX1 retry.

The original R26 physical candidate is preserved as immutable failure evidence.
FIX1 changes only two generated surfaces:

* the resident MC68EC000 wait hook preserves D4/current MIDI channel across the
  R25 release-retirement scheduler loop; and
* the SH-2 diagnostic screen renders PASS only when the R26 proof phase is PASS.

All source MIDI/profile, 16-voice policy, provisional RR16 envelope, FRT clock,
batching and final-state verification contracts remain the accepted R26 design.
"""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_physical_candidate_full_build_gate as _gate
from .midi_68k_r26_fix1_physical_candidate import derive_r26_fix1_candidate_main
from .midi_68k_r26_fix1_resident_audio_service import (
    build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image,
    render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_header,
    render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_source,
)


R26_FIX1_RELEASE_RATE = _gate.ACCEPTED_R26_RELEASE_RATE


class SaturnMidi68KR26Fix1FullBuildGateError(RuntimeError):
    """Raised when the fresh FIX1 candidate cannot be prepared or built."""


@contextmanager
def _patched_fix1_gate(*, release_rate: int):
    image = build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(
        release_rate=release_rate
    )
    names = (
        "build_srk_saturn_midi_68k_r26_resident_audio_service_image",
        "render_srk_saturn_midi_68k_r26_resident_audio_service_header",
        "render_srk_saturn_midi_68k_r26_resident_audio_service_source",
        "derive_r26_double_impact_candidate_main",
        "ACCEPTED_R26_IMAGE_SHA256",
        "ACCEPTED_R26_IMAGE_WORDS",
        "ACCEPTED_R26_IMAGE_BYTES",
    )
    original = {name: getattr(_gate, name) for name in names}
    try:
        _gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image = (
            build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image
        )
        _gate.render_srk_saturn_midi_68k_r26_resident_audio_service_header = (
            render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_header
        )
        _gate.render_srk_saturn_midi_68k_r26_resident_audio_service_source = (
            render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_source
        )
        _gate.derive_r26_double_impact_candidate_main = derive_r26_fix1_candidate_main
        _gate.ACCEPTED_R26_IMAGE_SHA256 = image.sha256
        _gate.ACCEPTED_R26_IMAGE_WORDS = image.word_count
        _gate.ACCEPTED_R26_IMAGE_BYTES = image.byte_size
        yield image
    finally:
        for name, value in original.items():
            setattr(_gate, name, value)


def run_saturn_midi_68k_r26_fix1_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    release_rate: int = R26_FIX1_RELEASE_RATE,
):
    """Build a fresh FIX1 candidate without mutating the original R26 gate."""

    if release_rate != R26_FIX1_RELEASE_RATE:
        raise SaturnMidi68KR26Fix1FullBuildGateError(
            "FIX1 must preserve the physically exercised provisional R26 RR16 policy"
        )
    try:
        with _patched_fix1_gate(release_rate=release_rate) as image:
            result = _gate.run_saturn_midi_68k_r26_physical_candidate_full_build_gate(
                baseline_project,
                repository_root,
                output_directory,
                release_rate=release_rate,
            )
    except Exception:
        raise

    if result.prepared.resident_image_sha256 != image.sha256:
        raise SaturnMidi68KR26Fix1FullBuildGateError(
            "fresh FIX1 candidate did not embed the repaired resident image"
        )
    return result
