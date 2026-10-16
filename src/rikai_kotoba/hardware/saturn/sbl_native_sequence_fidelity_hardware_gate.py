"""Preserve-first hardware gate for the provenance-locked corrected GATE3F candidate.

Only the exact Eridu-accepted GATE3F-LOCKED evidence may cross this gate.  The
finished local candidate is first re-audited with the media-blind fidelity
pre-media gate; its accepted manifest/build/media hashes are then hard-locked.
A SAROO write, when explicitly requested with the dedicated confirmation token,
is limited to one fresh destination directory and protected by a whole-card
inventory before and after the copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .saroo.card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from .saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN as STANDALONE_CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentPlan,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)
from .sbl_native_sequence_fidelity_pre_media import (
    SaturnSblNativeSequenceFidelityPreMediaReport,
    audit_gate3f_pre_media,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-NATIVE-SPACE-SPECTRE-GATE3F"
DEFAULT_DESTINATION_NAME = "SRK-Space-Spectre-SBL-NATIVE-GATE3F"

EXPECTED_MANIFEST_SHA256 = "e26309b105082e6cec23a7faa445113b4d2aa034931190fde8ba8be9d5f92303"
EXPECTED_BUILD_REPORT_SHA256 = "6e795aeba5ea5e0a148669f5671d3ae35b6fe02a98717db70370ab1a602e6174"
EXPECTED_BIN_BYTES = 752_640
EXPECTED_BIN_SHA256 = "006c037998696d584a3053aa60f6d3fb602b4aad1b36e2552f44aefb008d5130"
EXPECTED_CUE_BYTES = 81
EXPECTED_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"


class SaturnSblNativeSequenceFidelityHardwareGateError(RuntimeError):
    """Raised when corrected GATE3F cannot safely cross the media boundary."""


@dataclass(frozen=True)
class SaturnSblNativeSequenceFidelityHardwareEvidence:
    pre_media: SaturnSblNativeSequenceFidelityPreMediaReport
    plan: SarooStandaloneImageDeploymentPlan


@dataclass(frozen=True)
class SaturnSblNativeSequenceFidelityHardwareResult:
    evidence: SaturnSblNativeSequenceFidelityHardwareEvidence
    guard: SarooCardInventoryResult | None
    deployment: SarooStandaloneImageDeploymentResult | None
    verification: SarooCardInventoryVerification | None

    @property
    def applied(self) -> bool:
        return self.deployment is not None

    @property
    def card_verified(self) -> bool:
        return self.verification is not None and self.verification.valid


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _expect(actual, expected, label: str) -> None:
    if actual != expected:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"GATE3F hardware lock mismatch for {label}: expected {expected!r}, got {actual!r}"
        )


def _validate_locked_pre_media(project_directory) -> SaturnSblNativeSequenceFidelityPreMediaReport:
    try:
        report = audit_gate3f_pre_media(project_directory)
    except Exception as exc:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"GATE3F pre-media audit rejected candidate: {exc}"
        ) from exc

    _expect(report.manifest_sha256, EXPECTED_MANIFEST_SHA256, "manifest SHA-256")
    _expect(report.build_report_sha256, EXPECTED_BUILD_REPORT_SHA256, "build-report SHA-256")
    _expect(report.bin_bytes, EXPECTED_BIN_BYTES, "deployable BIN bytes")
    _expect(report.bin_sha256, EXPECTED_BIN_SHA256, "deployable BIN SHA-256")
    _expect(report.cue_bytes, EXPECTED_CUE_BYTES, "deployable CUE bytes")
    _expect(report.cue_sha256, EXPECTED_CUE_SHA256, "deployable CUE SHA-256")
    _expect(report.runtime_contract_exact, True, "runtime contract")
    _expect(report.deployable_verified_against_iso, True, "BIN/CUE ISO verification")
    return report


def inspect_gate3f_hardware_gate(
    project_directory,
    card_root,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
) -> SaturnSblNativeSequenceFidelityHardwareEvidence:
    """Perform the complete read-only GATE3F candidate/card deployment review."""

    pre_media = _validate_locked_pre_media(project_directory)
    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            project_directory,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"read-only SAROO deployment plan rejected GATE3F: {exc}"
        ) from exc

    _expect(plan.bin_size, EXPECTED_BIN_BYTES, "planned BIN bytes")
    _expect(plan.bin_sha256, EXPECTED_BIN_SHA256, "planned BIN SHA-256")
    _expect(plan.cue_size, EXPECTED_CUE_BYTES, "planned CUE bytes")
    _expect(plan.cue_sha256, EXPECTED_CUE_SHA256, "planned CUE SHA-256")
    return SaturnSblNativeSequenceFidelityHardwareEvidence(pre_media, plan)


def _allowed_paths(plan: SarooStandaloneImageDeploymentPlan) -> tuple[str, str, str]:
    try:
        destination = plan.destination_directory.relative_to(plan.card_root).as_posix()
    except ValueError as exc:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            "planned GATE3F destination is outside the mounted SAROO card"
        ) from exc
    return (
        destination,
        f"{destination}/{plan.source_bin.name}",
        f"{destination}/{plan.source_cue.name}",
    )


def run_gate3f_hardware_gate(
    project_directory,
    card_root,
    guard_manifest,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
    apply: bool = False,
    confirmation: str = "",
) -> SaturnSblNativeSequenceFidelityHardwareResult:
    """Revalidate GATE3F and optionally deploy one fresh guarded SAROO directory."""

    if apply and confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    guard_path = _canonical(guard_manifest)
    if _inside(guard_path, card):
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            "whole-card guard manifest must be stored outside the SAROO card"
        )

    evidence = inspect_gate3f_hardware_gate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    if not apply:
        return SaturnSblNativeSequenceFidelityHardwareResult(evidence, None, None, None)

    try:
        guard = create_saroo_card_inventory(card, guard_path)
        pre_verify = verify_saroo_card_inventory(card, guard.manifest_path)
    except Exception as exc:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"cannot establish fresh whole-card SAROO baseline: {exc}"
        ) from exc
    if not pre_verify.valid:
        detail = "; ".join(pre_verify.differences[:8])
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            "fresh whole-card SAROO baseline did not immediately verify: " + detail
        )

    before_write = inspect_gate3f_hardware_gate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    for actual, expected, label in (
        (before_write.pre_media.manifest_sha256, evidence.pre_media.manifest_sha256, "manifest changed before write"),
        (before_write.pre_media.build_report_sha256, evidence.pre_media.build_report_sha256, "build report changed before write"),
        (before_write.plan.bin_sha256, evidence.plan.bin_sha256, "BIN changed before write"),
        (before_write.plan.cue_sha256, evidence.plan.cue_sha256, "CUE changed before write"),
    ):
        _expect(actual, expected, label)

    try:
        deployment = apply_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=destination_name,
            category=category,
            confirmation=STANDALONE_CONFIRMATION_TOKEN,
        )
    except Exception as exc:
        try:
            state = verify_saroo_card_inventory(card, guard.manifest_path)
            detail = (
                "original whole-card baseline still matches"
                if state.valid
                else "card differs from baseline: " + "; ".join(state.differences[:8])
            )
        except Exception as verify_exc:
            detail = f"card state could not be rechecked: {verify_exc}"
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            f"GATE3F deployment failed; {detail}: {exc}"
        ) from exc

    _expect(deployment.bin_sha256, EXPECTED_BIN_SHA256, "deployed BIN SHA-256")
    _expect(deployment.cue_sha256, EXPECTED_CUE_SHA256, "deployed CUE SHA-256")

    try:
        verification = verify_saroo_card_inventory(
            card,
            guard.manifest_path,
            allowed_changed_paths=_allowed_paths(deployment.plan),
        )
    except Exception as exc:
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            "GATE3F was written but whole-card verification could not run; "
            "do not retry, delete or alter the card until reviewed: " + str(exc)
        ) from exc
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        raise SaturnSblNativeSequenceFidelityHardwareGateError(
            "GATE3F was written but whole-card guard found an unauthorized difference; "
            "do not retry, delete or alter the card until reviewed: " + detail
        )

    return SaturnSblNativeSequenceFidelityHardwareResult(
        evidence,
        guard,
        deployment,
        verification,
    )
