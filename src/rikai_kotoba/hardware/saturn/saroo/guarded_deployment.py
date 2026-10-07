"""Whole-card guarded SAROO Saturn-firmware apply and restore.

This layer composes the preserve-first firmware deployment primitives with the
read-only SAROO card inventory guard.  The user-facing write path is therefore
not allowed to rely only on the firmware hash: the reviewed off-card inventory
must match before a write, and every unrelated card path must still match after
that write.

Only ``SAROO/ssfirm.bin`` is authorised to differ during an apply/restore cycle.
Game images, configuration, MCU/FPGA firmware, and all other card content remain
outside the mutation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Iterable

from .card_guard import (
    SarooCardInventoryError,
    SarooCardInventoryVerification,
    verify_saroo_card_inventory,
)
from .deployment import (
    SarooDeploymentApplyResult,
    SarooDeploymentRestoreResult,
    apply_saroo_firmware,
    restore_saroo_firmware,
)


_AUTHORISED_FIRMWARE_PATH = "SAROO/ssfirm.bin"


class SarooGuardedDeploymentError(RuntimeError):
    """Raised when the whole-card deployment guard cannot prove a safe state."""


@dataclass(frozen=True)
class SarooGuardedApplyResult:
    deployment: SarooDeploymentApplyResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard: SarooCardInventoryVerification
    post_guard: SarooCardInventoryVerification


@dataclass(frozen=True)
class SarooGuardedRestoreResult:
    deployment: SarooDeploymentRestoreResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard: SarooCardInventoryVerification
    post_guard: SarooCardInventoryVerification


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validated_sha256(value: str, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SarooGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 hex digest"
        )
    return text


def _reviewed_manifest(
    card_root: os.PathLike[str] | str,
    manifest_path: os.PathLike[str] | str,
    expected_manifest_sha256: str,
) -> tuple[Path, str]:
    card = _canonical(card_root)
    manifest = _canonical(manifest_path)
    expected = _validated_sha256(
        expected_manifest_sha256,
        label="expected guard manifest hash",
    )

    if _inside(manifest, card):
        raise SarooGuardedDeploymentError(
            "whole-card guard manifest must be stored outside the mounted SAROO card"
        )
    if not manifest.is_file():
        raise SarooGuardedDeploymentError(
            f"whole-card guard manifest is not a file: {manifest}"
        )

    try:
        with manifest.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise SarooGuardedDeploymentError(
            f"cannot read whole-card guard manifest {manifest}: {exc}"
        ) from exc

    recorded = document.get("manifest_sha256") if isinstance(document, dict) else None
    if not isinstance(recorded, str):
        raise SarooGuardedDeploymentError(
            "whole-card guard manifest is missing manifest_sha256"
        )
    if recorded.lower() != expected:
        raise SarooGuardedDeploymentError(
            "whole-card guard manifest hash does not match the reviewed baseline"
        )
    return manifest, expected


def _guard_check(
    card_root: os.PathLike[str] | str,
    manifest_path: os.PathLike[str] | str,
    expected_manifest_sha256: str,
    *,
    allowed_changed_paths: Iterable[str] = (),
) -> tuple[Path, str, SarooCardInventoryVerification]:
    manifest, expected = _reviewed_manifest(
        card_root,
        manifest_path,
        expected_manifest_sha256,
    )
    try:
        verification = verify_saroo_card_inventory(
            card_root,
            manifest,
            allowed_changed_paths=allowed_changed_paths,
        )
    except SarooCardInventoryError as exc:
        raise SarooGuardedDeploymentError(str(exc)) from exc

    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        if len(verification.differences) > 8:
            detail += f"; ... {len(verification.differences) - 8} more"
        raise SarooGuardedDeploymentError(
            "whole-card guard mismatch: " + detail
        )
    return manifest, expected, verification


def apply_saroo_firmware_guarded(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_existing_sha256: str,
    expected_candidate_sha256: str,
) -> SarooGuardedApplyResult:
    """Apply ``SAROO/ssfirm.bin`` only inside a verified whole-card baseline.

    Before the firmware operation the card must match the reviewed inventory
    exactly.  After the firmware operation the same inventory must still match
    with only ``SAROO/ssfirm.bin`` authorised to differ.

    If the post-apply whole-card guard fails, SRK attempts to restore the
    verified off-card baseline firmware and then requires the complete original
    inventory to match again before reporting a verified rollback.
    """

    manifest, manifest_hash, pre_guard = _guard_check(
        card_root,
        guard_manifest,
        expected_guard_manifest_sha256,
    )

    try:
        deployment = apply_saroo_firmware(
            card_root,
            candidate_firmware,
            backup_root,
            expected_existing_sha256=expected_existing_sha256,
            expected_candidate_sha256=expected_candidate_sha256,
        )
    except Exception as exc:
        try:
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
            )
        except Exception as guard_exc:
            raise SarooGuardedDeploymentError(
                "firmware apply failed and the exact whole-card baseline can no "
                f"longer be verified: {exc}; guard: {guard_exc}"
            ) from exc
        raise SarooGuardedDeploymentError(
            f"firmware apply failed; whole-card baseline still verifies exactly: {exc}"
        ) from exc

    try:
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
                expected_current_sha256=deployment.candidate_sha256,
                expected_backup_sha256=deployment.previous_sha256,
                archive_root=deployment.backup_path.parent,
            )
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
            )
            rollback_state = "verified whole-card baseline rollback succeeded"
        except Exception as rollback_exc:
            rollback_state = (
                "rollback could not restore the verified whole-card baseline: "
                f"{rollback_exc}"
            )
        raise SarooGuardedDeploymentError(
            f"post-apply whole-card guard failed: {guard_exc}; {rollback_state}"
        ) from guard_exc

    return SarooGuardedApplyResult(
        deployment=deployment,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_hash,
        pre_guard=pre_guard,
        post_guard=post_guard,
    )


def restore_saroo_firmware_guarded(
    card_root: os.PathLike[str] | str,
    backup_firmware: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_current_sha256: str,
    expected_backup_sha256: str,
    archive_root: os.PathLike[str] | str | None = None,
) -> SarooGuardedRestoreResult:
    """Restore the baseline while proving unrelated card content stayed intact.

    The pre-restore guard permits only ``SAROO/ssfirm.bin`` to differ from the
    original baseline.  After restore, the complete card inventory must match
    the reviewed baseline exactly.
    """

    manifest, manifest_hash, pre_guard = _guard_check(
        card_root,
        guard_manifest,
        expected_guard_manifest_sha256,
        allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
    )

    try:
        deployment = restore_saroo_firmware(
            card_root,
            backup_firmware,
            expected_current_sha256=expected_current_sha256,
            expected_backup_sha256=expected_backup_sha256,
            archive_root=archive_root,
        )
    except Exception as exc:
        try:
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
                allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
            )
        except Exception as guard_exc:
            raise SarooGuardedDeploymentError(
                "firmware restore failed and the pre-restore whole-card state can "
                f"no longer be verified: {exc}; guard: {guard_exc}"
            ) from exc
        raise SarooGuardedDeploymentError(
            f"firmware restore failed; pre-restore whole-card state still verifies: {exc}"
        ) from exc

    try:
        _, _, post_guard = _guard_check(
            card_root,
            manifest,
            manifest_hash,
        )
    except Exception as guard_exc:
        rollback_state: str
        try:
            restore_saroo_firmware(
                card_root,
                deployment.pre_restore_archive_path,
                expected_current_sha256=deployment.restored_sha256,
                expected_backup_sha256=deployment.replaced_sha256,
                archive_root=deployment.pre_restore_archive_path.parent,
            )
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
                allowed_changed_paths=(_AUTHORISED_FIRMWARE_PATH,),
            )
            rollback_state = "verified pre-restore whole-card state rollback succeeded"
        except Exception as rollback_exc:
            rollback_state = (
                "rollback could not restore the verified pre-restore card state: "
                f"{rollback_exc}"
            )
        raise SarooGuardedDeploymentError(
            f"post-restore whole-card guard failed: {guard_exc}; {rollback_state}"
        ) from guard_exc

    return SarooGuardedRestoreResult(
        deployment=deployment,
        guard_manifest_path=manifest,
        guard_manifest_sha256=manifest_hash,
        pre_guard=pre_guard,
        post_guard=post_guard,
    )
