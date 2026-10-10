"""Two-phase whole-card guarded deployment for SRK's R19 silent batch candidate.

PREPARE re-runs the independent R19 pre-media gate, creates a fresh off-card
inventory of the complete mounted SAROO card, and verifies that inventory
without modifying the card.

APPLY requires the exact reviewed guard-manifest SHA-256 and an R19-specific
confirmation token.  It re-runs the pre-media gate, requires the whole card to
still match the prepared baseline exactly, writes only one fresh standalone
image directory through the existing verified deployment primitive, and then
requires the whole card to differ only by that directory and its verified
BIN/CUE.

If the post-write guard fails, automatic rollback is allowed only when the new
directory still contains exactly the accepted R19 BIN/CUE.  After removal the
original whole-card inventory must verify exactly again.
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
from .midi_68k_silent_batch_physical_candidate_pre_media_gate import (
    SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult,
    inspect_midi_68k_silent_batch_physical_candidate_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-R19-SILENT-BATCH-PROOF"


class SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(RuntimeError):
    """Raised when the R19 guarded media boundary cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchPhysicalCandidateGuardPrepareResult:
    pre_media: SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentResult:
    pre_media: SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult
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
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
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
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
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
    raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _saroo_guard_key(path: Path) -> str:
    """Return a stable card-inventory key despite Windows long/8.3 root aliases."""

    parts = path.parts
    matches = [
        index
        for index in range(len(parts) - 1)
        if parts[index].casefold() == "saroo" and parts[index + 1].casefold() == "iso"
    ]
    if len(matches) != 1:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"deployed path does not contain one unambiguous SAROO/ISO suffix: {path}"
        )
    return Path(*parts[matches[0] :]).as_posix()


def _allowed_paths(
    card_root: Path,
    deployment: SarooStandaloneImageDeploymentResult,
) -> tuple[str, ...]:
    del card_root
    paths = (
        deployment.plan.destination_directory,
        deployment.destination_bin,
        deployment.destination_cue,
    )
    return tuple(_saroo_guard_key(path) for path in paths)


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
        return f"automatic rollback failed while removing the isolated R19 directory: {exc}"

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed R19 but original whole-card baseline could not be checked: {exc}"
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        return (
            "rollback removed R19 but original whole-card baseline still mismatches: "
            + detail
        )
    return "verified rollback succeeded; original whole-card baseline restored"


def prepare_midi_68k_silent_batch_physical_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KSilentBatchPhysicalCandidateGuardPrepareResult:
    """Revalidate R19 and create a fresh off-card whole-card baseline."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )

    pre_media = inspect_midi_68k_silent_batch_physical_candidate_pre_media(
        project_directory,
        card,
        expected_image_sha256=expected_image_sha256,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
        destination_name=destination_name,
        category=category,
    )
    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"cannot establish fresh whole-card deployment baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")

    return SaturnMidi68KSilentBatchPhysicalCandidateGuardPrepareResult(
        pre_media=pre_media,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_midi_68k_silent_batch_physical_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_image_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
    confirmation: str,
) -> SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentResult:
    """Deploy R19 only inside the exact reviewed whole-card baseline."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    manifest, manifest_sha = _review_guard_manifest(
        card,
        guard_manifest,
        expected_guard_manifest_sha256,
    )

    pre_media = inspect_midi_68k_silent_batch_physical_candidate_pre_media(
        project_directory,
        card,
        expected_image_sha256=expected_image_sha256,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
        destination_name=destination_name,
        category=category,
    )

    try:
        pre_guard = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
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
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"R19 deployment failed; {state}: {exc}"
        ) from exc

    expected_bin = _validated_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _validated_sha256(expected_cue_sha256, "expected CUE SHA-256")
    if deployment.bin_sha256.lower() != expected_bin:
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            "deployed BIN hash does not match the externally accepted R19 artifact; "
            + rollback_state
        )
    if deployment.cue_sha256.lower() != expected_cue:
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            "deployed CUE hash does not match the externally accepted R19 artifact; "
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
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            f"post-deployment whole-card guard could not run: {exc}; {rollback_state}"
        ) from exc

    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback_state = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentError(
            "post-deployment whole-card guard found an unauthorised difference: "
            f"{detail}; {rollback_state}"
        )

    return SaturnMidi68KSilentBatchPhysicalCandidateGuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
