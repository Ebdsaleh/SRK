"""Two-phase whole-card guarded deployment for the approved SBL MIDI calibration image.

PREPARE re-runs the read-only calibration pre-media gate, locks the exact GATE3
manifest/report/BIN/CUE hashes, validates the existing modern SAROO layout, and
creates a whole-card inventory manifest outside the card with zero card writes.

APPLY requires the reviewed guard-manifest SHA-256 plus a calibration-specific
confirmation token. It re-runs all evidence checks, requires the whole card to
match the prepared inventory exactly, writes only one fresh TEST directory via
the generic verified standalone deployment primitive, and permits only that new
directory plus its BIN/CUE to differ afterward.
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
    SarooStandaloneImageDeploymentPlan,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)
from .sbl_midi_calibration_pre_media import (
    SaturnSblMidiCalibrationPreMediaReport,
    audit_midi_calibration_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-MIDI-CALIBRATION-GATE3"
DESTINATION_NAME = "SRK-Diagnostics-SBL-MIDI-CAL-GATE3"
CATEGORY = "TEST"

EXPECTED_MANIFEST_SHA256 = (
    "cdbb9896eafd57ed4e00793be61a7f3b2331644e6a084b26dcb8ccbae139376e"
)
EXPECTED_BUILD_REPORT_SHA256 = (
    "68ed42a9aac1cae2944d549e9a4624e1a5e647eb76820190dc4ab0cde672b2dc"
)
EXPECTED_BIN_SHA256 = (
    "3c021003718cb1146c5d2b3ccef0fe98018e07ac54023ef66406c2dbf4d7e1fc"
)
EXPECTED_CUE_SHA256 = (
    "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
)


class SaturnSblMidiCalibrationGuardedDeploymentError(RuntimeError):
    """Raised when the approved calibration image cannot cross the media boundary."""


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGuardPrepareResult:
    pre_media: SaturnSblMidiCalibrationPreMediaReport
    plan: SarooStandaloneImageDeploymentPlan
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGuardedDeploymentResult:
    pre_media: SaturnSblMidiCalibrationPreMediaReport
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
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
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
    raise SaturnSblMidiCalibrationGuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _validate_pre_media(
    report: SaturnSblMidiCalibrationPreMediaReport,
) -> None:
    expected = {
        "manifest SHA-256": (report.manifest_sha256, EXPECTED_MANIFEST_SHA256),
        "build-report SHA-256": (
            report.build_report_sha256,
            EXPECTED_BUILD_REPORT_SHA256,
        ),
        "deployable BIN SHA-256": (report.bin_sha256, EXPECTED_BIN_SHA256),
        "deployable CUE SHA-256": (report.cue_sha256, EXPECTED_CUE_SHA256),
    }
    for label, (actual, wanted) in expected.items():
        if actual.lower() != wanted:
            raise SaturnSblMidiCalibrationGuardedDeploymentError(
                f"calibration {label} no longer matches approved GATE3 evidence"
            )
    if not report.runtime_contract_exact:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "calibration Direct-MIDI runtime contract is no longer exact"
        )
    if not report.raw_scsp_callbacks_disabled:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "calibration raw-SCSP callbacks are no longer disabled"
        )
    if not report.deployable_verified_against_iso:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "calibration deployable is no longer verified against the ISO"
        )


def _audit(project_directory: os.PathLike[str] | str) -> SaturnSblMidiCalibrationPreMediaReport:
    report = audit_midi_calibration_pre_media(project_directory)
    _validate_pre_media(report)
    return report


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
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "whole-card guard manifest hash does not match the reviewed baseline"
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
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
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
    """Rollback only when the isolated destination is exactly the two copied files."""

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
        wanted = expected.get(child.name.casefold())
        if wanted is None:
            return "automatic rollback not attempted: destination contains an unexpected file"
        try:
            actual = _sha256_file(child)
        except OSError as exc:
            return f"automatic rollback not attempted: cannot hash destination file: {exc}"
        if actual.lower() != wanted:
            return "automatic rollback not attempted: destination file hash changed"

    try:
        for child in children:
            child.unlink()
        destination.rmdir()
    except OSError as exc:
        return f"automatic rollback failed while removing isolated calibration directory: {exc}"

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed calibration directory but baseline check failed: {exc}"
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        return "rollback removed calibration directory but baseline still mismatches: " + detail
    return "verified rollback succeeded; original whole-card baseline restored"


def prepare_sbl_midi_calibration_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
) -> SaturnSblMidiCalibrationGuardPrepareResult:
    """Create the off-card whole-card baseline with zero writes to the SAROO card."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )

    pre_media = _audit(project_directory)
    try:
        plan = plan_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=DESTINATION_NAME,
            category=CATEGORY,
        )
    except Exception as exc:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot establish safe calibration deployment plan: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "planned BIN no longer matches approved GATE3 hash"
        )
    if plan.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "planned CUE no longer matches approved GATE3 hash"
        )

    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot establish fresh calibration whole-card baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")
    return SaturnSblMidiCalibrationGuardPrepareResult(
        pre_media=pre_media,
        plan=plan,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_sbl_midi_calibration_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    confirmation: str,
) -> SaturnSblMidiCalibrationGuardedDeploymentResult:
    """Deploy only after exact revalidation of GATE3 and the prepared whole card."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    manifest, manifest_sha = _review_guard_manifest(
        card,
        guard_manifest,
        expected_guard_manifest_sha256,
    )
    pre_media = _audit(project_directory)

    try:
        plan = plan_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=DESTINATION_NAME,
            category=CATEGORY,
        )
    except Exception as exc:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot revalidate calibration deployment plan: {exc}"
        ) from exc
    if (
        plan.bin_sha256.lower() != EXPECTED_BIN_SHA256
        or plan.cue_sha256.lower() != EXPECTED_CUE_SHA256
    ):
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "deployment plan artifacts no longer match approved GATE3 hashes"
        )

    try:
        pre_guard = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot verify whole-card baseline immediately before deployment: {exc}"
        ) from exc
    _require_guard_valid(pre_guard, "pre-deployment")

    try:
        deployment = apply_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=DESTINATION_NAME,
            category=CATEGORY,
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
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"calibration deployment failed; {state}: {exc}"
        ) from exc

    if deployment.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "deployed BIN hash differs from approved GATE3 artifact; " + rollback
        )
    if deployment.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "deployed CUE hash differs from approved GATE3 artifact; " + rollback
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
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            f"cannot perform post-write whole-card verification; {rollback}: {exc}"
        ) from exc
    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGuardedDeploymentError(
            "post-write whole-card guard found an unauthorized difference: "
            + detail
            + "; "
            + rollback
        )

    return SaturnSblMidiCalibrationGuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
