"""Guarded transitions between already accepted SAROO research firmware builds.

The first guarded apply starts from the exact whole-card baseline.  Later SRK
research builds necessarily start from a card whose ``SAROO/ssfirm.bin`` already
differs from that original baseline.  This module permits exactly that one
pre-existing difference while continuing to require every unrelated card entry
to match the reviewed baseline.

Before replacement, the currently installed firmware is preserved off-card by
the existing content-addressed backup primitive.  After replacement, only
``SAROO/ssfirm.bin`` may differ from the original whole-card manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .deployment import (
    SarooDeploymentApplyResult,
    apply_saroo_firmware,
    restore_saroo_firmware,
)
from .guarded_deployment import (
    SarooGuardedDeploymentError,
    _AUTHORISED_FIRMWARE_PATH,
    _guard_check,
)
from .sd_layout import SAROO_SD_LAYOUT_MODERN, inspect_saroo_sd_layout


@dataclass(frozen=True)
class SarooGuardedTransitionResult:
    deployment: SarooDeploymentApplyResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard_valid: bool
    post_guard_valid: bool


def _validated_sha256(value: str, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SarooGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 hex digest"
        )
    return text


def _require_card_firmware_hash(
    card_root: os.PathLike[str] | str,
    expected_sha256: str,
    *,
    context: str,
) -> None:
    report = inspect_saroo_sd_layout(card_root)
    if report.layout != SAROO_SD_LAYOUT_MODERN or len(report.firmware_files) != 1:
        raise SarooGuardedDeploymentError(
            f"{context}: card is not exactly one modern SAROO/ssfirm.bin layout"
        )
    actual = report.firmware_files[0].sha256
    if actual != expected_sha256:
        raise SarooGuardedDeploymentError(
            f"{context}: card firmware hash mismatch "
            f"(expected {expected_sha256}, found {actual})"
        )


def transition_saroo_firmware_guarded(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_current_sha256: str,
    expected_candidate_sha256: str,
) -> SarooGuardedTransitionResult:
    """Replace one accepted research firmware with another under the card guard.

    The original whole-card manifest remains authoritative for every path except
    ``SAROO/ssfirm.bin``.  The caller must also provide the exact hash of the
    currently accepted firmware, so allowing the firmware path to differ never
    means accepting an unknown firmware state.
    """

    current_expected = _validated_sha256(
        expected_current_sha256,
        label="expected current firmware hash",
    )
    candidate_expected = _validated_sha256(
        expected_candidate_sha256,
        label="expected candidate firmware hash",
    )
    if current_expected == candidate_expected:
        raise SarooGuardedDeploymentError(
            "current and candidate firmware hashes are identical; transition is unnecessary"
        )

    manifest, manifest_hash, pre_guard = _guard_check(
        card_root,
        guard_manifest,
        expected_guard_manifest_sha256,
        allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
    )
    _require_card_firmware_hash(
        card_root,
        current_expected,
        context="pre-transition validation",
    )

    try:
        deployment = apply_saroo_firmware(
            card_root,
            candidate_firmware,
            backup_root,
            expected_existing_sha256=current_expected,
            expected_candidate_sha256=candidate_expected,
        )
    except Exception as exc:
        try:
            _require_card_firmware_hash(
                card_root,
                current_expected,
                context="failed-transition recovery check",
            )
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
                allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
            )
        except Exception as recovery_exc:
            raise SarooGuardedDeploymentError(
                "firmware transition failed and the accepted pre-transition state "
                f"can no longer be verified: {exc}; recovery check: {recovery_exc}"
            ) from exc
        raise SarooGuardedDeploymentError(
            f"firmware transition failed; accepted pre-transition state still verifies: {exc}"
        ) from exc

    try:
        _require_card_firmware_hash(
            card_root,
            candidate_expected,
            context="post-transition validation",
        )
        _, _, post_guard = _guard_check(
            card_root,
            manifest,
            manifest_hash,
            allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
        )
    except Exception as guard_exc:
        rollback_state: str
        try:
            restore_saroo_firmware(
                card_root,
                deployment.backup_path,
                expected_current_sha256=candidate_expected,
                expected_backup_sha256=current_expected,
                archive_root=deployment.backup_path.parent,
            )
            _require_card_firmware_hash(
                card_root,
                current_expected,
                context="transition rollback validation",
            )
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
                allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
            )
            rollback_state = "verified accepted-firmware rollback succeeded"
        except Exception as rollback_exc:
            rollback_state = (
                "rollback could not restore the accepted pre-transition state: "
                f"{rollback_exc}"
            )
        raise SarooGuardedDeploymentError(
            f"post-transition guard failed: {guard_exc}; {rollback_state}"
        ) from guard_exc

    return SarooGuardedTransitionResult(
        deployment=deployment,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_hash,
        pre_guard_valid=pre_guard.valid,
        post_guard_valid=post_guard.valid,
    )
