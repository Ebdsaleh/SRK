"""Guarded transitions between already accepted SAROO research firmware builds.

The first guarded apply starts from the exact whole-card baseline. Later SRK
research builds necessarily start from a card whose ``SAROO/ssfirm.bin`` already
differs from that original baseline and may also contain SRK's reviewed research
outputs. This module permits only those narrow research paths while continuing
to require every unrelated card entry to match the baseline.

SAROO's own ``SAROO/SS_SAVE.BIN`` is a legitimate mutable save container. It is
*not* exempted by default. A caller may explicitly review one exact save state by
supplying both its current byte size and SHA-256. That exact state is then
preserved off-card, admitted through the pre/post whole-card guard, and required
to remain byte-for-byte unchanged during the firmware transition.

Before replacement, the currently installed firmware is preserved off-card by
the existing content-addressed backup primitive. After replacement, the same
narrow research-output allowance is re-verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .deployment import (
    SarooDeploymentApplyResult,
    _copy_new_verified,
    _hash_file,
    apply_saroo_firmware,
    restore_saroo_firmware,
)
from .guarded_deployment import (
    SarooGuardedDeploymentError,
    _AUTHORISED_FIRMWARE_PATH,
    _guard_check,
)
from .sd_layout import SAROO_SD_LAYOUT_MODERN, inspect_saroo_sd_layout


SAROO_TRANSITION_RESEARCH_OUTPUT_SIZES = {
    "SAROO/SRK_WRAML.BIN": 0x00100000,
    "SAROO/SRK_WRAMH.BIN": 0x00100000,
    "SAROO/SRK_GAME_WRAMH.BIN": 0x00100000,
    "SAROO/SRK_RUNTIME_PROOF.BIN": 96,
    "SAROO/SRK_RUNTIME_INPUT_PROOF.BIN": 96,
}
SAROO_TRANSITION_RESEARCH_OUTPUTS = tuple(SAROO_TRANSITION_RESEARCH_OUTPUT_SIZES)
_SAROO_SAVE_PATH = "SAROO/SS_SAVE.BIN"
_SAROO_SAVE_BLOCK_SIZE = 0x00010000
_BASE_ALLOWED_TRANSITION_PATHS = (
    _AUTHORISED_FIRMWARE_PATH,
) + SAROO_TRANSITION_RESEARCH_OUTPUTS


@dataclass(frozen=True)
class SarooGuardedTransitionResult:
    deployment: SarooDeploymentApplyResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    pre_guard_valid: bool
    post_guard_valid: bool
    reviewed_save_path: Path | None = None
    reviewed_save_backup_path: Path | None = None
    reviewed_save_sha256: str | None = None
    reviewed_save_size: int | None = None
    reviewed_save_backup_reused: bool = False


def _validated_sha256(value: str, *, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise SarooGuardedDeploymentError(
            f"{label} must be a full 64-character SHA-256 hex digest"
        )
    return text


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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


def _validate_research_outputs(card_root: os.PathLike[str] | str) -> None:
    """Validate SRK-created research files before exempting them from baseline diffing."""

    card = Path(card_root).expanduser().resolve(strict=False)
    for relative, expected_size in SAROO_TRANSITION_RESEARCH_OUTPUT_SIZES.items():
        path = card / Path(relative)
        if not path.exists():
            continue
        if not path.is_file():
            raise SarooGuardedDeploymentError(
                f"reviewed SRK research output is not a file: {relative}"
            )
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise SarooGuardedDeploymentError(
                f"cannot inspect SRK research output {relative}: {exc}"
            ) from exc
        if size != expected_size:
            raise SarooGuardedDeploymentError(
                f"reviewed SRK research output has unexpected size: {relative} "
                f"({size} != {expected_size})"
            )


def _validate_reviewed_save(
    card_root: os.PathLike[str] | str,
    *,
    expected_sha256: str | None,
    expected_size: int | None,
) -> tuple[Path | None, str | None, int | None]:
    """Validate one explicitly reviewed exact ``SS_SAVE.BIN`` state.

    The absence of both expectations means the save file receives no guard
    exemption. Supplying only one expectation is rejected. SAROO stores this
    container as one 64 KiB index block followed by 64 KiB per-game save blocks,
    so reviewed sizes must be positive multiples of 64 KiB.
    """

    if expected_sha256 is None and expected_size is None:
        return None, None, None
    if expected_sha256 is None or expected_size is None:
        raise SarooGuardedDeploymentError(
            "reviewed SS_SAVE.BIN requires both expected SHA-256 and expected size"
        )
    if isinstance(expected_size, bool) or not isinstance(expected_size, int):
        raise SarooGuardedDeploymentError("expected SS_SAVE.BIN size must be an integer")
    if expected_size < _SAROO_SAVE_BLOCK_SIZE or expected_size % _SAROO_SAVE_BLOCK_SIZE:
        raise SarooGuardedDeploymentError(
            "expected SS_SAVE.BIN size must be a positive 64 KiB multiple"
        )

    expected_hash = _validated_sha256(
        expected_sha256,
        label="expected SS_SAVE.BIN hash",
    )
    card = Path(card_root).expanduser().resolve(strict=False)
    save_path = card / Path(_SAROO_SAVE_PATH)
    if not save_path.is_file():
        raise SarooGuardedDeploymentError(
            f"reviewed SAROO save container is missing or not a file: {_SAROO_SAVE_PATH}"
        )
    try:
        actual_size = save_path.stat().st_size
    except OSError as exc:
        raise SarooGuardedDeploymentError(
            f"cannot inspect reviewed SAROO save container {_SAROO_SAVE_PATH}: {exc}"
        ) from exc
    if actual_size != expected_size:
        raise SarooGuardedDeploymentError(
            "reviewed SS_SAVE.BIN size mismatch "
            f"(expected {expected_size}, found {actual_size})"
        )
    actual_hash = _hash_file(save_path, error_type=SarooGuardedDeploymentError)
    if actual_hash != expected_hash:
        raise SarooGuardedDeploymentError(
            "reviewed SS_SAVE.BIN hash mismatch "
            f"(expected {expected_hash}, found {actual_hash})"
        )
    return save_path, expected_hash, expected_size


def _preserve_reviewed_save(
    save_path: Path,
    backup_root: os.PathLike[str] | str,
    expected_sha256: str,
) -> tuple[Path, bool]:
    card_root = save_path.parents[1].resolve(strict=False)
    backup = Path(backup_root).expanduser().resolve(strict=False)
    if _inside(backup, card_root):
        raise SarooGuardedDeploymentError(
            "SS_SAVE.BIN preservation directory must be outside the mounted SAROO card"
        )
    destination = backup / f"SS_SAVE_{expected_sha256[:16]}.BIN"
    reused = _copy_new_verified(
        save_path,
        destination,
        expected_sha256,
        error_type=SarooGuardedDeploymentError,
    )
    return destination, reused


def transition_saroo_firmware_guarded(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    expected_guard_manifest_sha256: str,
    expected_current_sha256: str,
    expected_candidate_sha256: str,
    expected_ss_save_sha256: str | None = None,
    expected_ss_save_size: int | None = None,
) -> SarooGuardedTransitionResult:
    """Replace one accepted research firmware with another under the card guard.

    The original whole-card manifest remains authoritative for every path except
    ``SAROO/ssfirm.bin`` and the exact reviewed SRK research-output paths. The
    caller must provide the exact hash of the currently accepted firmware. Any
    present SRK research output must match its exact known format size before
    exemption.

    ``SAROO/SS_SAVE.BIN`` remains protected by default. It is exempted only when
    the caller supplies both its exact current SHA-256 and exact current size.
    That reviewed state is preserved off-card before the firmware write and must
    remain unchanged through the post-transition guard.
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

    reviewed_save_path, reviewed_save_hash, reviewed_save_size = _validate_reviewed_save(
        card_root,
        expected_sha256=expected_ss_save_sha256,
        expected_size=expected_ss_save_size,
    )
    allowed_transition_paths = _BASE_ALLOWED_TRANSITION_PATHS
    if reviewed_save_path is not None:
        allowed_transition_paths += (_SAROO_SAVE_PATH,)

    _validate_research_outputs(card_root)
    manifest, manifest_hash, pre_guard = _guard_check(
        card_root,
        guard_manifest,
        expected_guard_manifest_sha256,
        allowed_changed_paths=allowed_transition_paths,
    )
    _require_card_firmware_hash(
        card_root,
        current_expected,
        context="pre-transition validation",
    )

    reviewed_save_backup_path: Path | None = None
    reviewed_save_backup_reused = False
    if reviewed_save_path is not None and reviewed_save_hash is not None:
        reviewed_save_backup_path, reviewed_save_backup_reused = _preserve_reviewed_save(
            reviewed_save_path,
            backup_root,
            reviewed_save_hash,
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
            _validate_research_outputs(card_root)
            _validate_reviewed_save(
                card_root,
                expected_sha256=reviewed_save_hash,
                expected_size=reviewed_save_size,
            )
            _require_card_firmware_hash(
                card_root,
                current_expected,
                context="failed-transition recovery check",
            )
            _guard_check(
                card_root,
                manifest,
                manifest_hash,
                allowed_changed_paths=allowed_transition_paths,
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
        _validate_research_outputs(card_root)
        _validate_reviewed_save(
            card_root,
            expected_sha256=reviewed_save_hash,
            expected_size=reviewed_save_size,
        )
        _require_card_firmware_hash(
            card_root,
            candidate_expected,
            context="post-transition validation",
        )
        _, _, post_guard = _guard_check(
            card_root,
            manifest,
            manifest_hash,
            allowed_changed_paths=allowed_transition_paths,
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
            _validate_research_outputs(card_root)
            _validate_reviewed_save(
                card_root,
                expected_sha256=reviewed_save_hash,
                expected_size=reviewed_save_size,
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
                allowed_changed_paths=allowed_transition_paths,
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
        reviewed_save_path=reviewed_save_path,
        reviewed_save_backup_path=reviewed_save_backup_path,
        reviewed_save_sha256=reviewed_save_hash,
        reviewed_save_size=reviewed_save_size,
        reviewed_save_backup_reused=reviewed_save_backup_reused,
    )