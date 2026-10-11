"""Two-phase whole-card guarded deployment wrapper for corrected R22A."""

from __future__ import annotations

import os

from . import midi_68k_resident_stream_physical_candidate_guarded_deployment as _base
from .midi_68k_resident_stream_physical_candidate_r22a_pre_media_gate import (
    inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-R22A-STREAM-SCHEDULER-PROOF"

SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardPrepareResult = (
    _base.SaturnMidi68KResidentStreamPhysicalCandidateGuardPrepareResult
)
SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardedDeploymentResult = (
    _base.SaturnMidi68KResidentStreamPhysicalCandidateGuardedDeploymentResult
)


class SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardedDeploymentError(RuntimeError):
    """Raised when corrected R22A cannot cross the reviewed media boundary."""


def _inspect_r22a(project_directory, card_root, **kwargs):
    return inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media(
        project_directory,
        card_root,
        **kwargs,
    )


def _patch_base():
    return _base._inspect_pre_media, _base.CONFIRMATION_TOKEN


def _install_patch() -> None:
    _base._inspect_pre_media = _inspect_r22a
    _base.CONFIRMATION_TOKEN = CONFIRMATION_TOKEN


def _restore_patch(original_inspect, original_token) -> None:
    _base._inspect_pre_media = original_inspect
    _base.CONFIRMATION_TOKEN = original_token


def prepare_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardPrepareResult:
    original_inspect, original_token = _patch_base()
    _install_patch()
    try:
        try:
            return _base.prepare_midi_68k_resident_stream_physical_candidate_guarded_deployment(
                project_directory,
                card_root,
                guard_manifest,
                **kwargs,
            )
        except _base.SaturnMidi68KResidentStreamPhysicalCandidateGuardedDeploymentError as exc:
            raise SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardedDeploymentError(
                str(exc)
            ) from exc
    finally:
        _restore_patch(original_inspect, original_token)


def apply_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardedDeploymentResult:
    original_inspect, original_token = _patch_base()
    _install_patch()
    try:
        try:
            return _base.apply_midi_68k_resident_stream_physical_candidate_guarded_deployment(
                project_directory,
                card_root,
                guard_manifest,
                **kwargs,
            )
        except _base.SaturnMidi68KResidentStreamPhysicalCandidateGuardedDeploymentError as exc:
            raise SaturnMidi68KResidentStreamPhysicalCandidateR22AGuardedDeploymentError(
                str(exc)
            ) from exc
    finally:
        _restore_patch(original_inspect, original_token)
