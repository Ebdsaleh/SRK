"""Two-phase whole-card guarded deployment for the R18 silent MIDI/68K candidate.

Phase 1 is prepare-only: re-run the independent pre-media gate, then create a
fresh off-card inventory of the entire mounted SAROO card.  The card is read
only in this phase.

Phase 2 requires the exact reviewed inventory manifest/hash plus an explicit
R18-specific confirmation token.  The candidate is revalidated again, the card
must still match the whole-card baseline exactly, and the existing verified
standalone image deployment primitive writes one new game directory only.
Afterward the whole card must still match the baseline with exactly the new R18
directory/BIN/CUE authorised to differ.

If that post-write guard fails, SRK removes the new directory automatically only
when it still contains exactly the verified candidate BIN/CUE, then requires the
original whole-card inventory to match again before reporting a verified
rollback.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN as STANDALONE_DEPLOYMENT_CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
)
from .midi_68k_physical_proof_candidate_pre_media_gate import (
    SaturnMidi68KPhysicalProofCandidatePreMediaResult,
    inspect_midi_68k_physical_proof_candidate_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-R18-SILENT-PROOF"


class SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(RuntimeError):
    """Raised when the R18 guarded media boundary cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCandidateGuardPrepareResult:
    pre_media: SaturnMidi68KPhysicalProofCandidatePreMediaResult
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCandidateGuardedDeploymentResult:
    pre_media: SaturnMidi68KPhysicalProofCandidatePreMediaResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard: SarooCardInventoryVerification
    deployment: SarooStandaloneImageDeploymentResult
    post_guard: SarooCardInventoryVerification
    allowed_changed_paths: tuple[str, ...]


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_sha256(value: str, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 hex digest"
        )
    return normalized


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _review_guard_manifest(
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    expected_guard_manifest_sha256: str,
) -> tuple[Path, str]:
    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    expected = _validated_sha256(
        expected_guard_manifest_sha256,
        "expected guard manifest SHA-256",
    )
    if _inside(manifest, card):
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "whole-card guard manifest hash does not match the reviewed baseline"
        )
    return manifest, expected


def _require_guard_valid(
    verification: SarooCardInventoryVerification,
    label: str,
) -> None:
    if verification.valid:
        return
    detail = "; ".join(verification.differences[:8])
    if len(verification.differences) > 8:
        detail += f"; ... {len(verification.differences) - 8} more"
    raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _allowed_paths(
    card_root: Path,
    deployment: SarooStandaloneImageDeploymentResult,
) -> tuple[str, ...]:
    paths = (
        deployment.plan.destination_directory,
        deployment.destination_bin,
        deployment.destination_cue,
    )
    return tuple(path.relative_to(card_root).as_posix() for path in paths)


def _safe_rollback_new_directory(
    card_root: Path,
    deployment: SarooStandaloneImageDeploymentResult,
    guard_manifest: Path,
) -> str:
    destination = deployment.plan.destination_directory
    if not destination.is_dir():
        return "automatic rollback not attempted: deployed destination is missing"

    try:
        children = sorted(destination.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        return f"automatic rollback not attempted: cannot inspect destination: {exc}"

    expected = {
        deployment.destination_bin.name.casefold(): deployment.bin_sha256.lower(),
        deployment.destination_cue.name.casefold(): deployment.cue_sha256.lower(),
    }
    if len(children) != 2:
        return "automatic rollback not attempted: destination contains unexpected entries"

    for child in children:
        if child.is_symlink() or not child.is_file():
            return "automatic rollback not attempted: destination contains a non-regular file"
        expected_sha = expected.get(child.name.casefold())
        if expected_sha is None:
            return "automatic rollback not attempted: destination contains an unexpected file"
        try:
            actual_sha = _sha256_file(child)
        except OSError as exc:
            return f"automatic rollback not attempted: cannot hash destination file: {exc}"
        if actual_sha.lower() != expected_sha:
            return "automatic rollback not attempted: destination file hash changed"

    try:
        for child in children:
            child.unlink()
        destination.rmdir()
    except OSError as exc:
        return f"automatic rollback failed while removing the isolated R18 directory: {exc}"

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed R18 but original whole-card baseline could not be checked: {exc}"
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        return (
            "rollback removed R18 but original whole-card baseline still mismatches: "
            + detail
        )
    return "verified rollback succeeded; original whole-card baseline restored"


def prepare_midi_68k_physical_proof_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KPhysicalProofCandidateGuardPrepareResult:
    """Create a fresh off-card whole-card baseline after re-running pre-media checks."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )

    pre_media = inspect_midi_68k_physical_proof_candidate_pre_media(
        project_directory,
        card,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
        destination_name=destination_name,
        category=category,
    )
    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"cannot establish fresh whole-card deployment baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")

    return SaturnMidi68KPhysicalProofCandidateGuardPrepareResult(
        pre_media=pre_media,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_midi_68k_physical_proof_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
    confirmation: str,
) -> SaturnMidi68KPhysicalProofCandidateGuardedDeploymentResult:
    """Deploy R18 only inside the exact reviewed whole-card baseline."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    manifest, manifest_sha = _review_guard_manifest(
        card,
        guard_manifest,
        expected_guard_manifest_sha256,
    )

    pre_media = inspect_midi_68k_physical_proof_candidate_pre_media(
        project_directory,
        card,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
        destination_name=destination_name,
        category=category,
    )

    try:
        pre_guard = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"cannot verify whole-card baseline immediately before deployment: {exc}"
        ) from exc
    _require_guard_valid(pre_guard, "pre-deployment")

    try:
        deployment = apply_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=destination_name,
            category=category,
            confirmation=STANDALONE_DEPLOYMENT_CONFIRMATION_TOKEN,
        )
    except Exception as exc:
        try:
            after_failure = verify_saroo_card_inventory(card, manifest)
            if after_failure.valid:
                state = "original whole-card baseline still verifies exactly"
            else:
                detail = "; ".join(after_failure.differences[:8])
                state = "whole-card baseline no longer matches: " + detail
        except Exception as guard_exc:
            state = f"whole-card state could not be verified: {guard_exc}"
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"R18 deployment failed; {state}: {exc}"
        ) from exc

    expected_bin = _validated_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _validated_sha256(expected_cue_sha256, "expected CUE SHA-256")
    if deployment.bin_sha256.lower() != expected_bin:
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "deployed BIN hash does not match the externally accepted R18 artifact; "
            + rollback_state
        )
    if deployment.cue_sha256.lower() != expected_cue:
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "deployed CUE hash does not match the externally accepted R18 artifact; "
            + rollback_state
        )

    allowed = _allowed_paths(card, deployment)
    try:
        post_guard = verify_saroo_card_inventory(
            card,
            manifest,
            allowed_changed_paths=allowed,
        )
    except Exception as exc:
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            f"post-deployment whole-card guard could not run: {exc}; {rollback_state}"
        ) from exc

    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KPhysicalProofCandidateGuardedDeploymentError(
            "post-deployment whole-card guard found an unauthorised difference: "
            f"{detail}; {rollback_state}"
        )

    return SaturnMidi68KPhysicalProofCandidateGuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
