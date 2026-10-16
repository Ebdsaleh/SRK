"""Two-phase whole-card guarded deployment for SBL MIDI calibration GATE4.

PREPARE re-runs the read-only GATE4 pre-media audit, locks the exact accepted
manifest/report/map/BIN/CUE hashes, validates the existing SAROO layout and
creates a whole-card inventory manifest outside the card with zero card writes.

APPLY requires the reviewed guard-manifest SHA-256 and a GATE4-specific
confirmation token. It revalidates everything immediately before copying and
permits only one fresh TEST directory plus its verified BIN/CUE to differ.
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
from .sbl_midi_calibration_gate4_pre_media import (
    SaturnSblMidiCalibrationGate4PreMediaReport,
    audit_sbl_midi_calibration_gate4_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-MIDI-CALIBRATION-GATE4"
DESTINATION_NAME = "SRK-Diagnostics-SBL-MIDI-CAL-GATE4"
CATEGORY = "TEST"

EXPECTED_MANIFEST_SHA256 = (
    "5aecb9b4d660fa6618f3a60217a762a200c1f5be74a2d30af8109707ef4fd8ba"
)
EXPECTED_BUILD_REPORT_SHA256 = (
    "b63b64b4b74dcc64af376084ba1eaf2fa947497718e7234bf244051951864df5"
)
EXPECTED_AREA_MAP_SHA256 = (
    "b4a249b0d9df4985ad6f3357cd978e017b41bbf82d0d6603f378d968c6b67001"
)
EXPECTED_BIN_SHA256 = (
    "78af4a56160f5ce1ff4778b313ad233a5014c7cbd274cb4d25515b22f87947d0"
)
EXPECTED_CUE_SHA256 = (
    "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
)


class SaturnSblMidiCalibrationGate4GuardedDeploymentError(RuntimeError):
    """Raised when GATE4 cannot cross the reviewed SAROO media boundary."""


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGate4GuardPrepareResult:
    pre_media: SaturnSblMidiCalibrationGate4PreMediaReport
    plan: SarooStandaloneImageDeploymentPlan
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGate4GuardedDeploymentResult:
    pre_media: SaturnSblMidiCalibrationGate4PreMediaReport
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
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
    raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _validate_pre_media(report: SaturnSblMidiCalibrationGate4PreMediaReport) -> None:
    expected = {
        "manifest SHA-256": (report.manifest_sha256, EXPECTED_MANIFEST_SHA256),
        "build-report SHA-256": (
            report.build_report_sha256,
            EXPECTED_BUILD_REPORT_SHA256,
        ),
        "external .MP SHA-256": (report.area_map_sha256, EXPECTED_AREA_MAP_SHA256),
        "deployable BIN SHA-256": (report.bin_sha256, EXPECTED_BIN_SHA256),
        "deployable CUE SHA-256": (report.cue_sha256, EXPECTED_CUE_SHA256),
    }
    for label, (actual, wanted) in expected.items():
        if actual.lower() != wanted:
            raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
                f"GATE4 {label} no longer matches accepted pre-media evidence"
            )
    if report.area_map_bytes != 18:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "GATE4 external .MP map is no longer exactly 18 bytes"
        )


def _audit(project_directory: os.PathLike[str] | str) -> SaturnSblMidiCalibrationGate4PreMediaReport:
    report = audit_sbl_midi_calibration_gate4_pre_media(project_directory)
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"cannot read whole-card guard manifest: {exc}"
        ) from exc
    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str) or recorded.lower() != expected:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "whole-card guard manifest hash does not match reviewed GATE4 baseline"
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
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
        return f"automatic rollback failed while removing isolated GATE4 directory: {exc}"

    try:
        verification = verify_saroo_card_inventory(card_root, guard_manifest)
    except Exception as exc:
        return f"rollback removed GATE4 directory but baseline check failed: {exc}"
    if not verification.valid:
        return (
            "rollback removed GATE4 directory but baseline still mismatches: "
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"cannot establish safe GATE4 deployment plan: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "planned BIN no longer matches accepted GATE4 artifact"
        )
    if plan.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "planned CUE no longer matches accepted GATE4 artifact"
        )
    return plan


def prepare_sbl_midi_calibration_gate4_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
) -> SaturnSblMidiCalibrationGate4GuardPrepareResult:
    """Revalidate GATE4 and create a fresh off-card whole-card baseline."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    if _inside(manifest, card):
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "whole-card guard manifest must be outside the mounted SAROO card"
        )
    pre_media = _audit(project_directory)
    plan = _plan(project_directory, card)
    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"cannot establish fresh GATE4 whole-card baseline: {exc}"
        ) from exc
    _require_guard_valid(verification, "prepare")
    return SaturnSblMidiCalibrationGate4GuardPrepareResult(
        pre_media=pre_media,
        plan=plan,
        guard_inventory=inventory,
        exact_verification=verification,
    )


def apply_sbl_midi_calibration_gate4_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    confirmation: str,
) -> SaturnSblMidiCalibrationGate4GuardedDeploymentResult:
    """Deploy GATE4 only inside the exact reviewed whole-card baseline."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"cannot verify GATE4 whole-card baseline before deployment: {exc}"
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"GATE4 deployment failed; {state}: {exc}"
        ) from exc

    if deployment.bin_sha256.lower() != EXPECTED_BIN_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "deployed BIN differs from accepted GATE4 artifact; " + rollback
        )
    if deployment.cue_sha256.lower() != EXPECTED_CUE_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "deployed CUE differs from accepted GATE4 artifact; " + rollback
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
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            f"cannot perform GATE4 post-write whole-card verification; {rollback}: {exc}"
        ) from exc
    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback = _safe_rollback_new_directory(card, deployment, manifest)
        raise SaturnSblMidiCalibrationGate4GuardedDeploymentError(
            "GATE4 post-write whole-card guard found an unauthorized difference: "
            + detail
            + "; "
            + rollback
        )

    return SaturnSblMidiCalibrationGate4GuardedDeploymentResult(
        pre_media=pre_media,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_sha,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
