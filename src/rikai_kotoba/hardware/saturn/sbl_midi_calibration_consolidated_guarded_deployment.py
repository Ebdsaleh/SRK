"""Two-phase whole-card guarded deployment for consolidated SBL MIDI calibration.

PREPARE re-runs the consolidated read-only pre-media audit, locks the exact
Sega one-shot map/BIN/CUE evidence plus the self-bound manifest/build report,
and writes only an off-card whole-card inventory manifest. APPLY requires the
reviewed guard-manifest SHA-256 plus a one-shot-specific confirmation token.
Only one fresh TEST directory and its verified BIN/CUE may differ from the
reviewed card baseline.
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
from .sbl_midi_calibration_consolidated_pre_media import (
    SaturnSblMidiCalibrationConsolidatedPreMediaReport,
    audit_consolidated_midi_calibration_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-MIDI-CALIBRATION-SEGA-ONESHOT"
DESTINATION_NAME = "SRK-Diagnostics-SBL-MIDI-CAL-SEGA-ONESHOT"
CATEGORY = "TEST"

EXPECTED_AREA_MAP_SHA256 = (
    "40530e1a0f1b147a6f87aaaa00de7593b82fbec806f291bcddc2b09d865a4605"
)
EXPECTED_BIN_SHA256 = (
    "56fc685e8df1e3f4f28806ef703bbfcc26b5bd48105a7aeae5917f7158f967ca"
)
EXPECTED_CUE_SHA256 = (
    "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
)
EXPECTED_PROGRAM_COUNT = 128
EXPECTED_FAMILY_COUNT = 16
EXPECTED_MAX_FAMILY_BYTES = 185568


class SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(RuntimeError):
    """Raised when consolidated calibration cannot cross the media boundary."""


@dataclass(frozen=True)
class SaturnSblMidiCalibrationConsolidatedGuardPrepareResult:
    pre_media: SaturnSblMidiCalibrationConsolidatedPreMediaReport
    plan: SarooStandaloneImageDeploymentPlan
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnSblMidiCalibrationConsolidatedGuardedDeploymentResult:
    pre_media: SaturnSblMidiCalibrationConsolidatedPreMediaReport
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard: SarooCardInventoryVerification
    deployment: SarooStandaloneImageDeploymentResult
    post_guard: SarooCardInventoryVerification
    allowed_changed_paths: tuple[str, ...]


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validated_sha256(value: str, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 digest"
        )
    return normalized


def _require_guard_valid(
    verification: SarooCardInventoryVerification,
    label: str,
) -> None:
    if verification.valid:
        return
    detail = "; ".join(verification.differences[:8])
    if len(verification.differences) > 8:
        detail += f"; ... {len(verification.differences) - 8} more"
    raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _validate_pre_media(
    report: SaturnSblMidiCalibrationConsolidatedPreMediaReport,
) -> None:
    expected = {
        "external .MP SHA-256": (report.area_map_sha256, EXPECTED_AREA_MAP_SHA256),
        "deployable BIN SHA-256": (report.bin_sha256, EXPECTED_BIN_SHA256),
        "deployable CUE SHA-256": (report.cue_sha256, EXPECTED_CUE_SHA256),
    }
    for label, (actual, wanted) in expected.items():
        if actual.lower() != wanted:
            raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
                f"consolidated {label} no longer matches accepted pre-media evidence"
            )
    for label, value in (
        ("manifest SHA-256", report.manifest_sha256),
        ("build-report SHA-256", report.build_report_sha256),
    ):
        _validated_sha256(value, f"consolidated {label}")
    if report.program_count != EXPECTED_PROGRAM_COUNT:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated GM program count is no longer 128"
        )
    if report.family_count != EXPECTED_FAMILY_COUNT:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated GM family count is no longer 16"
        )
    if report.largest_family_bytes != EXPECTED_MAX_FAMILY_BYTES:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated largest family size changed"
        )
    if not report.screen_owned_sbl_lifecycle:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated SBL lifecycle is no longer screen-owned"
        )
    if not report.raw_scsp_audio_test_retained:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated raw SCSP Audio Test is no longer retained"
        )
    if not report.driver_execution_telemetry:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated 68K execution telemetry is no longer present"
        )
    if not report.sega_oneshot_order:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated Sega Direct-MIDI one-shot order is no longer exact"
        )
    if not report.deployable_verified_against_iso:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "consolidated deployable is no longer verified against its ISO"
        )


def _audit(
    project_directory: os.PathLike[str] | str,
) -> SaturnSblMidiCalibrationConsolidatedPreMediaReport:
    report = audit_consolidated_midi_calibration_pre_media(project_directory)
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
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "whole-card guard manifest hash does not match reviewed consolidated baseline"
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
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"deployed path does not contain one unambiguous SAROO/ISO suffix: {path}"
        )
    return Path(*parts[matches[0] :]).as_posix()


def _allowed_paths(deployment: SarooStandaloneImageDeploymentResult) -> tuple[str, ...]:
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
        return (
            "automatic rollback failed while removing isolated consolidated one-shot directory: "
            f"{exc}"
        )

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed one-shot directory but baseline check failed: {exc}"
    if not verification.valid:
        return (
            "rollback removed one-shot directory but baseline still mismatches: "
            + "; ".join(verification.differences[:8])
        )
    return "verified rollback succeeded; original whole-card baseline restored"


def _plan(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
) -> SarooStandaloneImageDeploymentPlan:
    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            project_directory,
            destination_name=DESTINATION_NAME,
            category=CATEGORY,
        )
    except Exception as exc:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"cannot establish safe consolidated one-shot deployment plan: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "planned BIN no longer matches accepted Sega one-shot artifact"
        )
    if plan.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "planned CUE no longer matches accepted Sega one-shot artifact"
        )
    return plan


def prepare_sbl_midi_calibration_consolidated_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
) -> SaturnSblMidiCalibrationConsolidatedGuardPrepareResult:
    """Revalidate the one-shot image and create a fresh off-card baseline."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )
    pre_media = _audit(project_directory)
    plan = _plan(project_directory, card)
    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"cannot establish fresh consolidated one-shot whole-card baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")
    return SaturnSblMidiCalibrationConsolidatedGuardPrepareResult(
        pre_media=pre_media,
        plan=plan,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_sbl_midi_calibration_consolidated_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    confirmation: str,
) -> SaturnSblMidiCalibrationConsolidatedGuardedDeploymentResult:
    """Deploy only inside the exact reviewed whole-card baseline."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    manifest, manifest_sha = _review_guard_manifest(
        card,
        guard_manifest,
        expected_guard_manifest_sha256,
    )
    pre_media = _audit(project_directory)
    _plan(project_directory, card)

    try:
        pre_guard = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"cannot verify consolidated one-shot whole-card baseline before deployment: {exc}"
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
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            f"consolidated one-shot deployment failed; {state}: {exc}"
        ) from exc

    if deployment.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "deployed BIN differs from accepted Sega one-shot artifact; " + rollback
        )
    if deployment.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "deployed CUE differs from accepted Sega one-shot artifact; " + rollback
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
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "cannot perform one-shot post-write whole-card verification; "
            f"{rollback}: {exc}"
        ) from exc
    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
            "one-shot post-write whole-card guard found an unauthorized difference: "
            + detail
            + "; "
            + rollback
        )

    return SaturnSblMidiCalibrationConsolidatedGuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
