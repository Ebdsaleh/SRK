"""Two-phase whole-card guarded deployment for the R24 real-SMF proof.

PREPARE re-runs the independent R24 pre-media gate, binds the exact externally
accepted candidate manifest/report hashes, creates a fresh off-card inventory of
the complete mounted SAROO card and verifies it with zero card writes.

APPLY requires the exact reviewed guard-manifest SHA-256 and an R24-specific
confirmation token. It re-runs pre-media, requires an exact pre-write card
match, writes only one fresh standalone directory through the accepted generic
deployment primitive, and permits only that directory plus its BIN/CUE to differ.
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
from .midi_68k_r24_physical_candidate_pre_media_gate import (
    SaturnMidi68KR24PhysicalCandidatePreMediaResult,
    inspect_saturn_midi_68k_r24_physical_candidate_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-R24-REAL-SMF-SONG-PROOF"


class SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(RuntimeError):
    """Raised when R24 cannot cross the reviewed whole-card media boundary."""


@dataclass(frozen=True)
class SaturnMidi68KR24PhysicalCandidateGuardPrepareResult:
    pre_media: SaturnMidi68KR24PhysicalCandidatePreMediaResult
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnMidi68KR24PhysicalCandidateGuardedDeploymentResult:
    pre_media: SaturnMidi68KR24PhysicalCandidatePreMediaResult
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
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 hex digest"
        )
    return normalized


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_guard_valid(
    verification: SarooCardInventoryVerification,
    label: str,
) -> None:
    if verification.valid:
        return
    detail = "; ".join(verification.differences[:8])
    if len(verification.differences) > 8:
        detail += f"; ... {len(verification.differences) - 8} more"
    raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


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
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "whole-card guard manifest hash does not match the reviewed R24 baseline"
        )
    return manifest, expected


def _saroo_guard_key(path: Path) -> str:
    parts = path.parts
    matches = [
        index
        for index in range(len(parts) - 1)
        if parts[index].casefold() == "saroo" and parts[index + 1].casefold() == "iso"
    ]
    if len(matches) != 1:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"deployed path does not contain one unambiguous SAROO/ISO suffix: {path}"
        )
    return Path(*parts[matches[0] :]).as_posix()


def _allowed_paths(
    deployment: SarooStandaloneImageDeploymentResult,
) -> tuple[str, ...]:
    return tuple(
        _saroo_guard_key(path)
        for path in (
            deployment.plan.destination_directory,
            deployment.destination_bin,
            deployment.destination_cue,
        )
    )


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
        return f"automatic rollback failed while removing the isolated R24 directory: {exc}"

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed R24 but original whole-card baseline could not be checked: {exc}"
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        return "rollback removed R24 but original whole-card baseline still mismatches: " + detail
    return "verified rollback succeeded; original whole-card baseline restored"


def _inspect_pre_media(
    project_directory: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    **kwargs: object,
) -> SaturnMidi68KR24PhysicalCandidatePreMediaResult:
    return inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
        project_directory,
        source_midi,
        card_root,
        **kwargs,
    )


def _validate_external_candidate_chain(
    pre_media: SaturnMidi68KR24PhysicalCandidatePreMediaResult,
    *,
    expected_candidate_manifest_sha256: str,
    expected_candidate_report_sha256: str,
) -> None:
    expected_manifest = _validated_sha256(
        expected_candidate_manifest_sha256,
        "accepted R24 candidate manifest SHA-256",
    )
    expected_report = _validated_sha256(
        expected_candidate_report_sha256,
        "accepted R24 candidate build-report SHA-256",
    )
    if pre_media.manifest_sha256.lower() != expected_manifest:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "R24 candidate manifest no longer matches the independently accepted pre-media result"
        )
    if pre_media.report_sha256.lower() != expected_report:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "R24 candidate build report no longer matches the independently accepted pre-media result"
        )


def prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_candidate_manifest_sha256: str,
    expected_candidate_report_sha256: str,
    destination_name: str,
    category: str | None = None,
    **pre_media_kwargs: object,
) -> SaturnMidi68KR24PhysicalCandidateGuardPrepareResult:
    """Revalidate R24 and create a fresh off-card whole-card baseline."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )
    pre_media = _inspect_pre_media(
        project_directory,
        source_midi,
        card,
        destination_name=destination_name,
        category=category,
        **pre_media_kwargs,
    )
    _validate_external_candidate_chain(
        pre_media,
        expected_candidate_manifest_sha256=expected_candidate_manifest_sha256,
        expected_candidate_report_sha256=expected_candidate_report_sha256,
    )
    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"cannot establish fresh R24 whole-card deployment baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")
    return SaturnMidi68KR24PhysicalCandidateGuardPrepareResult(
        pre_media=pre_media,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_candidate_manifest_sha256: str,
    expected_candidate_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
    confirmation: str,
    **pre_media_kwargs: object,
) -> SaturnMidi68KR24PhysicalCandidateGuardedDeploymentResult:
    """Deploy R24 only inside the exact reviewed whole-card baseline."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    manifest, manifest_sha = _review_guard_manifest(
        card,
        guard_manifest,
        expected_guard_manifest_sha256,
    )
    pre_media = _inspect_pre_media(
        project_directory,
        source_midi,
        card,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
        destination_name=destination_name,
        category=category,
        **pre_media_kwargs,
    )
    _validate_external_candidate_chain(
        pre_media,
        expected_candidate_manifest_sha256=expected_candidate_manifest_sha256,
        expected_candidate_report_sha256=expected_candidate_report_sha256,
    )

    try:
        pre_guard = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"cannot verify R24 whole-card baseline immediately before deployment: {exc}"
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
            state = (
                "original whole-card baseline still verifies exactly"
                if after_failure.valid
                else "whole-card baseline no longer matches: "
                + "; ".join(after_failure.differences[:8])
            )
        except Exception as guard_exc:
            state = f"whole-card state could not be verified: {guard_exc}"
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"R24 deployment failed; {state}: {exc}"
        ) from exc

    expected_bin = _validated_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _validated_sha256(expected_cue_sha256, "expected CUE SHA-256")
    if deployment.bin_sha256.lower() != expected_bin:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "deployed BIN hash does not match externally accepted R24 artifact; " + rollback
        )
    if deployment.cue_sha256.lower() != expected_cue:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "deployed CUE hash does not match externally accepted R24 artifact; " + rollback
        )

    allowed = _allowed_paths(deployment)
    try:
        post_guard = verify_saroo_card_inventory(
            card,
            manifest,
            allowed_changed_paths=allowed,
        )
    except Exception as exc:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            f"cannot perform R24 post-write whole-card verification; {rollback}: {exc}"
        ) from exc
    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
            "R24 post-write whole-card guard found an unauthorized difference: "
            + detail
            + "; "
            + rollback
        )

    return SaturnMidi68KR24PhysicalCandidateGuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
