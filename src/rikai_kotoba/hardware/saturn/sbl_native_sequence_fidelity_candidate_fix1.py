"""Provenance fix for the locked corrected-tone GATE3F off-card builder.

The first GATE3F builder added its final fidelity-candidate policy marker after
standalone_build had already hashed the project manifest into
SRK_STANDALONE_BUILD.json.  Audio assets remained correct, but that post-build
manifest mutation made the build report's provenance hash stale.

This wrapper moves every final GATE3F policy marker into the temporary baseline
*before* the native candidate is generated/built, and suppresses the redundant
post-build annotation.  The resulting final manifest is therefore the exact
manifest hashed by the standalone build report.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path

from . import sbl_native_sequence_fidelity_candidate as _base


SaturnSblNativeSequenceFidelityCandidateError = (
    _base.SaturnSblNativeSequenceFidelityCandidateError
)
SaturnSblNativeSequenceFidelityCandidateResult = (
    _base.SaturnSblNativeSequenceFidelityCandidateResult
)

_ORIGINAL_STAGE = _base._stage_fidelity_baseline
_ORIGINAL_ANNOTATE = _base._annotate_final_manifest


def _stage_fidelity_baseline_with_final_policy(
    baseline: Path,
    destination: Path,
    melodic: bytes,
    drums: bytes,
    source_soundfont: Path,
) -> None:
    _ORIGINAL_STAGE(
        baseline,
        destination,
        melodic,
        drums,
        source_soundfont,
    )
    manifest_path = destination / _base._MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "staged GATE3F manifest is not an object"
        )
    policy = dict(manifest.get("policy") or {})
    policy.update(
        {
            "sbl_native_sequence_fidelity_gate3f": True,
            "gate3f_off_card_only": True,
            "saroo_writes": False,
            "hardware_executed_during_build": False,
        }
    )
    manifest["policy"] = policy
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _no_post_build_manifest_mutation(_output: Path, _source_soundfont: Path) -> None:
    """Intentionally do nothing: all fidelity metadata is authored pre-build."""


@contextmanager
def _provenance_patch():
    previous_stage = _base._stage_fidelity_baseline
    previous_annotate = _base._annotate_final_manifest
    _base._stage_fidelity_baseline = _stage_fidelity_baseline_with_final_policy
    _base._annotate_final_manifest = _no_post_build_manifest_mutation
    try:
        yield
    finally:
        _base._annotate_final_manifest = previous_annotate
        _base._stage_fidelity_baseline = previous_stage


def build_saturn_sbl_native_sequence_fidelity_candidate(
    failed_gate3e_project,
    baseline_project,
    sequence_directory,
    saturn_root,
    output_directory,
    soundfont=None,
) -> SaturnSblNativeSequenceFidelityCandidateResult:
    """Build GATE3F with manifest/build-report provenance kept byte-exact."""

    with _provenance_patch():
        return _base.build_saturn_sbl_native_sequence_fidelity_candidate(
            failed_gate3e_project,
            baseline_project,
            sequence_directory,
            saturn_root,
            output_directory,
            soundfont,
        )
