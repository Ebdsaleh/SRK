"""Fresh off-card full-build wrapper for R28 percussion fidelity pass 1.

R28 keeps the physically accepted R26 FIX1 transport plus R27 melodic/mixer
changes. Only channel-10 source shape, fixed drum playback-rate semantics,
normal-loop silent-tail LSA policy and diagnostic subtitle change.
"""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_physical_candidate_full_build_gate as _gate
from .midi_68k_r28_physical_candidate import derive_r28_percussion_candidate_main
from .midi_68k_r28_resident_audio_service import (
    build_srk_saturn_midi_68k_r28_resident_audio_service_image,
    render_srk_saturn_midi_68k_r28_resident_audio_service_header,
    render_srk_saturn_midi_68k_r28_resident_audio_service_source,
)


R28_RELEASE_RATE = _gate.ACCEPTED_R26_RELEASE_RATE


class SaturnMidi68KR28FullBuildGateError(RuntimeError):
    """Raised when the fresh R28 percussion candidate cannot be built."""


@contextmanager
def _patched_r28_gate(*, release_rate: int):
    image = build_srk_saturn_midi_68k_r28_resident_audio_service_image(
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
            build_srk_saturn_midi_68k_r28_resident_audio_service_image
        )
        _gate.render_srk_saturn_midi_68k_r26_resident_audio_service_header = (
            render_srk_saturn_midi_68k_r28_resident_audio_service_header
        )
        _gate.render_srk_saturn_midi_68k_r26_resident_audio_service_source = (
            render_srk_saturn_midi_68k_r28_resident_audio_service_source
        )
        _gate.derive_r26_double_impact_candidate_main = (
            derive_r28_percussion_candidate_main
        )
        _gate.ACCEPTED_R26_IMAGE_SHA256 = image.sha256
        _gate.ACCEPTED_R26_IMAGE_WORDS = image.word_count
        _gate.ACCEPTED_R26_IMAGE_BYTES = image.byte_size
        yield image
    finally:
        for name, value in original.items():
            setattr(_gate, name, value)


def run_saturn_midi_68k_r28_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    release_rate: int = R28_RELEASE_RATE,
):
    if release_rate != R28_RELEASE_RATE:
        raise SaturnMidi68KR28FullBuildGateError(
            "R28 must preserve the physically accepted provisional RR16 policy"
        )

    with _patched_r28_gate(release_rate=release_rate) as image:
        result = _gate.run_saturn_midi_68k_r26_physical_candidate_full_build_gate(
            baseline_project,
            repository_root,
            output_directory,
            release_rate=release_rate,
        )

    if result.prepared.resident_image_sha256 != image.sha256:
        raise SaturnMidi68KR28FullBuildGateError(
            "fresh R28 candidate did not embed the percussion resident image"
        )
    if result.prepared.record_count != _gate.ACCEPTED_R26_RECORDS:
        raise SaturnMidi68KR28FullBuildGateError("R28 changed the Space Spectre stream")
    if result.prepared.release_steal_count != _gate.ACCEPTED_R26_RELEASE_STEALS:
        raise SaturnMidi68KR28FullBuildGateError("R28 changed the host capacity model")
    return result
