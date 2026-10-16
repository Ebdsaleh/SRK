"""Build the locked corrected-tone native SDDRV GATE3F candidate off-card.

The physically failed GATE3E project remains the forensic reference.  Before a
new project is allowed to exist this module re-runs the in-memory fidelity proof,
regenerates the corrected melodic/drum TON bytes, requires the exact golden
hashes established on Eridu, injects those bytes into a temporary baseline, and
then delegates the native-sequence project build to the already validated GFS /
SND_StartSeq compatibility builder.

No SAROO path is accepted and no hardware is executed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from .sbl_fidelity_tone_authoring import build_space_spectre_fidelity_tone_banks
from .sbl_fidelity_tone_build_audit import (
    _requirements_from_scope,
    audit_space_spectre_fidelity_tone_build,
)
from .sbl_modulator_scope_audit import audit_space_spectre_modulator_scope
from .sbl_native_sequence_candidate_fix1 import (
    SaturnSblNativeSequenceCandidateResult,
    build_saturn_sbl_native_sequence_candidate,
)


class SaturnSblNativeSequenceFidelityCandidateError(RuntimeError):
    """Raised when the locked GATE3F off-card build cannot be proven safe."""


GATE3F_MELODIC_SHA256 = "2170b6145a250bf00abe915f523308ddb7377ee456ec7b01458afa2b7244e269"
GATE3F_DRUM_SHA256 = "15e4eee6b37548c9181a53906a73e3f8997c414a1538f2cceed3e25e79ab382f"
GATE3F_MELODIC_BYTES = 321_140
GATE3F_DRUM_BYTES = 111_786

_MELODIC_RELATIVE = "cd/SRKGM.BIN"
_DRUM_RELATIVE = "cd/SRKDRUM.BIN"
_MANIFEST = "SRK_STANDALONE_PROJECT.json"


@dataclass(frozen=True)
class SaturnSblNativeSequenceFidelityCandidateResult:
    candidate: SaturnSblNativeSequenceCandidateResult
    golden_melodic_sha256: str
    golden_drum_sha256: str
    golden_melodic_bytes: int
    golden_drum_bytes: int
    source_soundfont: Path


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _require_golden(label: str, payload: bytes, expected_sha: str, expected_bytes: int) -> None:
    actual_sha = _sha_bytes(payload)
    if len(payload) != expected_bytes or actual_sha != expected_sha:
        raise SaturnSblNativeSequenceFidelityCandidateError(
            f"{label} corrected TON lock changed: bytes={len(payload)} sha256={actual_sha}; "
            f"expected bytes={expected_bytes} sha256={expected_sha}"
        )


def _replace_manifest_hash(manifest: dict, relative: str, payload: bytes) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "baseline generated_files manifest is missing"
        )
    matches = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("path") == relative
    ]
    if len(matches) != 1:
        raise SaturnSblNativeSequenceFidelityCandidateError(
            f"baseline manifest does not uniquely contain {relative}"
        )
    matches[0]["sha256"] = _sha_bytes(payload)
    if "size" in matches[0]:
        matches[0]["size"] = len(payload)
    if "bytes" in matches[0]:
        matches[0]["bytes"] = len(payload)


def _stage_fidelity_baseline(
    baseline: Path,
    destination: Path,
    melodic: bytes,
    drums: bytes,
    source_soundfont: Path,
) -> None:
    shutil.copytree(baseline, destination, ignore=shutil.ignore_patterns("build"))
    melodic_path = destination / _MELODIC_RELATIVE
    drum_path = destination / _DRUM_RELATIVE
    manifest_path = destination / _MANIFEST
    if not melodic_path.is_file() or not drum_path.is_file() or not manifest_path.is_file():
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "baseline is missing tone-bank or project-manifest inputs"
        )

    melodic_path.write_bytes(melodic)
    drum_path.write_bytes(drums)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SaturnSblNativeSequenceFidelityCandidateError("baseline manifest is not an object")
    _replace_manifest_hash(manifest, _MELODIC_RELATIVE, melodic)
    _replace_manifest_hash(manifest, _DRUM_RELATIVE, drums)
    policy = dict(manifest.get("policy") or {})
    policy.update(
        {
            "sbl_fidelity_tone_policy": True,
            "soundfont_static_attenuation_compatibility_scale": 0.40,
            "multi_velocity_tables": True,
            "gate3f_off_card_only": True,
            "saroo_writes": False,
        }
    )
    manifest["policy"] = policy
    manifest["sbl_fidelity_tone_lock"] = {
        "schema": "srk.saturn.sbl-fidelity-tone-lock.v1",
        "source_soundfont": str(source_soundfont),
        "melodic_sha256": GATE3F_MELODIC_SHA256,
        "melodic_bytes": GATE3F_MELODIC_BYTES,
        "drum_sha256": GATE3F_DRUM_SHA256,
        "drum_bytes": GATE3F_DRUM_BYTES,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _annotate_final_manifest(output: Path, source_soundfont: Path) -> None:
    manifest_path = output / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "built GATE3F project manifest is missing"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "built GATE3F project manifest is invalid"
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
    manifest["sbl_fidelity_tone_lock"] = {
        "schema": "srk.saturn.sbl-fidelity-tone-lock.v1",
        "source_soundfont": str(source_soundfont),
        "melodic_sha256": GATE3F_MELODIC_SHA256,
        "melodic_bytes": GATE3F_MELODIC_BYTES,
        "drum_sha256": GATE3F_DRUM_SHA256,
        "drum_bytes": GATE3F_DRUM_BYTES,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_saturn_sbl_native_sequence_fidelity_candidate(
    failed_gate3e_project,
    baseline_project,
    sequence_directory,
    saturn_root,
    output_directory,
    soundfont=None,
) -> SaturnSblNativeSequenceFidelityCandidateResult:
    """Build GATE3F off-card using only the already-proven corrected TON bytes."""

    failed = Path(failed_gate3e_project).expanduser().resolve(strict=True)
    baseline = Path(baseline_project).expanduser().resolve(strict=True)
    sequence = Path(sequence_directory).expanduser().resolve(strict=True)
    saturn = Path(saturn_root).expanduser().resolve(strict=True)
    output = Path(output_directory).expanduser().resolve(strict=False)
    if output.exists():
        raise SaturnSblNativeSequenceFidelityCandidateError(
            f"output already exists; refusing overwrite: {output}"
        )

    proof = audit_space_spectre_fidelity_tone_build(failed, soundfont)
    if not (
        proof.historical_reproduced
        and proof.m6_exact
        and proof.row_count == 74
        and proof.pcm_identity_preserved
        and proof.pitch_identity_preserved
        and proof.static_total_levels_exact
        and proof.packed_assignments_exact
    ):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "corrected in-memory TON proof is not fully closed"
        )
    if (
        proof.melodic_sha256 != GATE3F_MELODIC_SHA256
        or proof.drum_sha256 != GATE3F_DRUM_SHA256
        or proof.melodic_bytes != GATE3F_MELODIC_BYTES
        or proof.drum_bytes != GATE3F_DRUM_BYTES
    ):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "corrected TON proof differs from locked GATE3F hashes"
        )

    scope = audit_space_spectre_modulator_scope(failed, soundfont)
    if scope.rows_with_other_attenuation_modulators:
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "used zones regained unresolved destination-48 modulators"
        )
    requirements = _requirements_from_scope(scope.rows)
    velocity_mapping = {
        row.key: row.velocity_attenuation_amount_cb for row in scope.rows
    }
    authored = build_space_spectre_fidelity_tone_banks(
        scope.soundfont_path,
        requirements,
        velocity_mapping,
    )
    melodic = authored.banks.melodic_bytes
    drums = authored.banks.drum_bytes
    _require_golden("melodic", melodic, GATE3F_MELODIC_SHA256, GATE3F_MELODIC_BYTES)
    _require_golden("drum", drums, GATE3F_DRUM_SHA256, GATE3F_DRUM_BYTES)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}.gate3f-", dir=str(output.parent)))
    staged_baseline = temp_root / "baseline"
    try:
        _stage_fidelity_baseline(
            baseline,
            staged_baseline,
            melodic,
            drums,
            scope.soundfont_path,
        )
        candidate = build_saturn_sbl_native_sequence_candidate(
            staged_baseline,
            sequence,
            saturn,
            output,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    built_melodic = output / _MELODIC_RELATIVE
    built_drums = output / _DRUM_RELATIVE
    if not built_melodic.is_file() or not built_drums.is_file():
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "built GATE3F project lost corrected tone-bank files"
        )
    _require_golden(
        "built melodic",
        built_melodic.read_bytes(),
        GATE3F_MELODIC_SHA256,
        GATE3F_MELODIC_BYTES,
    )
    _require_golden(
        "built drum",
        built_drums.read_bytes(),
        GATE3F_DRUM_SHA256,
        GATE3F_DRUM_BYTES,
    )
    if (
        candidate.assets.melodic_tone_bank_sha256 != GATE3F_MELODIC_SHA256
        or candidate.assets.drum_tone_bank_sha256 != GATE3F_DRUM_SHA256
    ):
        raise SaturnSblNativeSequenceFidelityCandidateError(
            "native candidate result hashes differ from corrected TON locks"
        )

    _annotate_final_manifest(output, scope.soundfont_path)
    return SaturnSblNativeSequenceFidelityCandidateResult(
        candidate=candidate,
        golden_melodic_sha256=GATE3F_MELODIC_SHA256,
        golden_drum_sha256=GATE3F_DRUM_SHA256,
        golden_melodic_bytes=GATE3F_MELODIC_BYTES,
        golden_drum_bytes=GATE3F_DRUM_BYTES,
        source_soundfont=scope.soundfont_path,
    )
