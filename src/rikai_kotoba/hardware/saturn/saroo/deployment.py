"""Preserve-first planning, backup, apply, and restore for SAROO Saturn firmware.

The user's existing SAROO SD card is treated as independent known-good evidence.
SRK never assumes that its current firmware came from the same upstream source
revision used for an SRK research build.

Planning is read-only. Backup writes only to an explicitly off-card location.
Apply and restore are explicit card-write operations gated by caller-supplied
SHA-256 expectations, verified off-card preservation, same-directory staging,
and post-write verification. Only modern ``SAROO/ssfirm.bin`` is eligible;
MCU/FPGA firmware is out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil

from .sd_layout import (
    SAROO_SD_LAYOUT_MODERN,
    SarooSdFileInfo,
    inspect_saroo_sd_layout,
)


class SarooDeploymentPlanError(RuntimeError):
    """Raised when a safe read-only deployment plan cannot be produced."""


class SarooDeploymentBackupError(RuntimeError):
    """Raised when a verified off-card baseline backup cannot be produced."""


class SarooDeploymentApplyError(RuntimeError):
    """Raised when a verified firmware apply cannot complete safely."""


class SarooDeploymentRestoreError(RuntimeError):
    """Raised when a verified firmware restore cannot complete safely."""


@dataclass(frozen=True)
class SarooDeploymentCandidate:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class SarooDeploymentPlan:
    card_root: Path
    layout: str
    existing_firmware: SarooSdFileInfo | None
    candidate: SarooDeploymentCandidate
    destination_relative_path: str | None
    backup_path: Path | None
    backup_already_valid: bool
    replacement_needed: bool
    ready_for_future_apply: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SarooDeploymentBackupResult:
    card_root: Path
    source_path: Path
    backup_path: Path
    firmware_sha256: str
    backup_reused: bool


@dataclass(frozen=True)
class SarooDeploymentApplyResult:
    card_root: Path
    destination_path: Path
    backup_path: Path
    previous_sha256: str
    candidate_sha256: str
    backup_reused: bool


@dataclass(frozen=True)
class SarooDeploymentRestoreResult:
    card_root: Path
    destination_path: Path
    backup_path: Path
    pre_restore_archive_path: Path
    replaced_sha256: str
    restored_sha256: str
    archive_reused: bool


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _hash_file(path: Path, *, error_type: type[RuntimeError] = SarooDeploymentPlanError) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise error_type(f"cannot read file {path}: {exc}") from exc
    return digest.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validated_sha256(value: str, *, label: str, error_type: type[RuntimeError]) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise error_type(f"{label} must be a full 64-character SHA-256 hex digest")
    return text


def _firmware_destination(
    card: Path,
    relative_path: str,
    *,
    error_type: type[RuntimeError],
) -> Path:
    parts = [part for part in relative_path.replace("\\", "/").split("/") if part]
    destination = card.joinpath(*parts)
    if not _inside(destination.resolve(strict=False), card):
        raise error_type("resolved firmware destination escaped the card root")
    return destination


def _copy_new_verified(
    source: Path,
    destination: Path,
    expected_sha256: str,
    *,
    error_type: type[RuntimeError],
) -> bool:
    """Create a content-verified file without overwriting conflicting content.

    Returns ``True`` when an already-valid destination was reused and ``False``
    when a new file was created.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file():
            raise error_type(f"preservation path exists but is not a file: {destination}")
        if _hash_file(destination, error_type=error_type) != expected_sha256:
            raise error_type(
                "preservation path already exists with different content; refusing overwrite: "
                f"{destination}"
            )
        return True

    temporary = destination.with_name(destination.name + ".srk-partial")
    if temporary.exists():
        raise error_type(f"stale temporary preservation file exists: {temporary}")

    try:
        try:
            with source.open("rb") as input_file, temporary.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
                output_file.flush()
                os.fsync(output_file.fileno())
        except OSError as exc:
            raise error_type(f"cannot create verified preservation copy: {exc}") from exc

        if _hash_file(temporary, error_type=error_type) != expected_sha256:
            raise error_type("new preservation copy failed SHA-256 verification")

        if destination.exists():
            if destination.is_file() and _hash_file(destination, error_type=error_type) == expected_sha256:
                temporary.unlink(missing_ok=True)
                return True
            raise error_type(
                "preservation destination appeared with conflicting content during copy: "
                f"{destination}"
            )

        try:
            temporary.rename(destination)
        except OSError as exc:
            raise error_type(f"cannot publish preservation copy {destination}: {exc}") from exc

        if _hash_file(destination, error_type=error_type) != expected_sha256:
            raise error_type("published preservation copy failed SHA-256 verification")
        return False
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def _stage_file(
    source: Path,
    temporary: Path,
    expected_sha256: str,
    *,
    error_type: type[RuntimeError],
) -> None:
    if temporary.exists():
        raise error_type(f"stale card staging file exists; refusing overwrite: {temporary}")
    try:
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
    except OSError as exc:
        raise error_type(f"cannot stage firmware beside card destination: {exc}") from exc
    if _hash_file(temporary, error_type=error_type) != expected_sha256:
        raise error_type("staged firmware failed SHA-256 verification")


def _rollback_destination(
    rollback_source: Path,
    destination: Path,
    expected_sha256: str,
    *,
    error_type: type[RuntimeError],
) -> bool:
    temporary = destination.with_name(destination.name + ".srk-rollback")
    try:
        _stage_file(
            rollback_source,
            temporary,
            expected_sha256,
            error_type=error_type,
        )
        os.replace(temporary, destination)
        return _hash_file(destination, error_type=error_type) == expected_sha256
    except Exception:
        return False
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _replace_verified(
    source: Path,
    destination: Path,
    *,
    expected_current_sha256: str,
    expected_new_sha256: str,
    rollback_source: Path,
    error_type: type[RuntimeError],
) -> None:
    temporary = destination.with_name(destination.name + ".srk-new")
    try:
        _stage_file(source, temporary, expected_new_sha256, error_type=error_type)

        current_hash = _hash_file(destination, error_type=error_type)
        if current_hash != expected_current_sha256:
            raise error_type(
                "card firmware changed after validation; refusing replacement "
                f"(expected {expected_current_sha256}, found {current_hash})"
            )

        try:
            os.replace(temporary, destination)
        except OSError as exc:
            raise error_type(f"cannot replace card firmware {destination}: {exc}") from exc

        written_hash = _hash_file(destination, error_type=error_type)
        if written_hash != expected_new_sha256:
            rolled_back = _rollback_destination(
                rollback_source,
                destination,
                expected_current_sha256,
                error_type=error_type,
            )
            state = "verified rollback succeeded" if rolled_back else "rollback could not be verified"
            raise error_type(
                "replacement failed post-write SHA-256 verification; " + state
            )
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def plan_saroo_firmware_deployment(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
) -> SarooDeploymentPlan:
    """Describe a future SAROO Saturn-firmware replacement without writing."""

    card = _canonical(card_root)
    candidate_path = _canonical(candidate_firmware)
    backups = _canonical(backup_root)

    if not candidate_path.is_file():
        raise SarooDeploymentPlanError(
            f"candidate Saturn firmware is not a file: {candidate_path}"
        )
    if _inside(candidate_path, card):
        raise SarooDeploymentPlanError(
            "candidate firmware must be outside the mounted SAROO SD card"
        )
    if _inside(backups, card):
        raise SarooDeploymentPlanError(
            "backup root must be outside the mounted SAROO SD card"
        )

    candidate = SarooDeploymentCandidate(
        path=candidate_path,
        size=candidate_path.stat().st_size,
        sha256=_hash_file(candidate_path),
    )

    report = inspect_saroo_sd_layout(card)
    warnings = list(report.warnings)

    if report.layout != SAROO_SD_LAYOUT_MODERN:
        warnings.append(
            "Deployment planning is gated to an unambiguous modern "
            "SAROO/ssfirm.bin card layout; no destination or backup is authorised."
        )
        return SarooDeploymentPlan(
            card_root=card,
            layout=report.layout,
            existing_firmware=report.firmware_files[0] if len(report.firmware_files) == 1 else None,
            candidate=candidate,
            destination_relative_path=None,
            backup_path=None,
            backup_already_valid=False,
            replacement_needed=True,
            ready_for_future_apply=False,
            warnings=tuple(warnings),
        )

    if len(report.firmware_files) != 1:
        raise SarooDeploymentPlanError(
            "modern SAROO layout did not resolve exactly one existing firmware file"
        )

    existing = report.firmware_files[0]
    destination = existing.relative_path
    replacement_needed = existing.sha256 != candidate.sha256
    backup_path = backups / f"ssfirm_{existing.sha256[:16]}.bin"

    backup_already_valid = False
    if backup_path.exists():
        if not backup_path.is_file():
            warnings.append(
                f"Proposed backup path already exists but is not a file: {backup_path}"
            )
        else:
            backup_hash = _hash_file(backup_path)
            if backup_hash == existing.sha256:
                backup_already_valid = True
            else:
                warnings.append(
                    "Proposed backup path already exists with different content; "
                    "a future apply must not overwrite it."
                )

    if not replacement_needed:
        warnings.append(
            "Candidate firmware is byte-identical to the existing card firmware; "
            "replacement is unnecessary."
        )

    backup_collision = backup_path.exists() and not backup_already_valid
    ready = replacement_needed and not backup_collision

    return SarooDeploymentPlan(
        card_root=card,
        layout=report.layout,
        existing_firmware=existing,
        candidate=candidate,
        destination_relative_path=destination,
        backup_path=backup_path,
        backup_already_valid=backup_already_valid,
        replacement_needed=replacement_needed,
        ready_for_future_apply=ready,
        warnings=tuple(warnings),
    )


def backup_saroo_firmware(
    card_root: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
    *,
    expected_existing_sha256: str,
) -> SarooDeploymentBackupResult:
    """Create or reuse a verified off-card backup without modifying the SD card."""

    expected_existing = _validated_sha256(
        expected_existing_sha256,
        label="expected existing firmware hash",
        error_type=SarooDeploymentBackupError,
    )
    card = _canonical(card_root)
    backups = _canonical(backup_root)
    if _inside(backups, card):
        raise SarooDeploymentBackupError(
            "backup root must be outside the mounted SAROO SD card"
        )

    report = inspect_saroo_sd_layout(card)
    if report.layout != SAROO_SD_LAYOUT_MODERN or len(report.firmware_files) != 1:
        raise SarooDeploymentBackupError(
            "backup is gated to exactly one modern SAROO/ssfirm.bin firmware file"
        )

    existing = report.firmware_files[0]
    if existing.sha256 != expected_existing:
        raise SarooDeploymentBackupError(
            "existing card firmware hash does not match the reviewed value"
        )

    source = _firmware_destination(
        card,
        existing.relative_path,
        error_type=SarooDeploymentBackupError,
    )
    backup_path = backups / f"ssfirm_{existing.sha256[:16]}.bin"
    reused = _copy_new_verified(
        source,
        backup_path,
        expected_existing,
        error_type=SarooDeploymentBackupError,
    )

    if _hash_file(source, error_type=SarooDeploymentBackupError) != expected_existing:
        raise SarooDeploymentBackupError(
            "card firmware changed while backup was being created; review card state before applying"
        )
    if _hash_file(backup_path, error_type=SarooDeploymentBackupError) != expected_existing:
        raise SarooDeploymentBackupError("off-card backup failed final SHA-256 verification")

    return SarooDeploymentBackupResult(
        card_root=card,
        source_path=source,
        backup_path=backup_path,
        firmware_sha256=expected_existing,
        backup_reused=reused,
    )


def apply_saroo_firmware(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
    *,
    expected_existing_sha256: str,
    expected_candidate_sha256: str,
) -> SarooDeploymentApplyResult:
    """Back up, verify, replace, and re-verify modern ``SAROO/ssfirm.bin``.

    The expected hashes must come from a previously reviewed deployment plan.
    This makes a stale plan fail closed if either the card or candidate changes.
    """

    expected_existing = _validated_sha256(
        expected_existing_sha256,
        label="expected existing firmware hash",
        error_type=SarooDeploymentApplyError,
    )
    expected_candidate = _validated_sha256(
        expected_candidate_sha256,
        label="expected candidate firmware hash",
        error_type=SarooDeploymentApplyError,
    )

    try:
        plan = plan_saroo_firmware_deployment(card_root, candidate_firmware, backup_root)
    except Exception as exc:
        raise SarooDeploymentApplyError(str(exc)) from exc

    if not plan.ready_for_future_apply or plan.existing_firmware is None:
        raise SarooDeploymentApplyError(
            "deployment plan is not ready for an explicit modern-layout apply"
        )
    if plan.destination_relative_path is None or plan.backup_path is None:
        raise SarooDeploymentApplyError("deployment plan did not authorise destination/backup")
    if plan.existing_firmware.sha256 != expected_existing:
        raise SarooDeploymentApplyError(
            "existing card firmware hash no longer matches the reviewed plan"
        )
    if plan.candidate.sha256 != expected_candidate:
        raise SarooDeploymentApplyError(
            "candidate firmware hash no longer matches the reviewed plan"
        )

    try:
        backup_result = backup_saroo_firmware(
            plan.card_root,
            backup_root,
            expected_existing_sha256=expected_existing,
        )
    except Exception as exc:
        raise SarooDeploymentApplyError(str(exc)) from exc

    destination = _firmware_destination(
        plan.card_root,
        plan.destination_relative_path,
        error_type=SarooDeploymentApplyError,
    )
    _replace_verified(
        plan.candidate.path,
        destination,
        expected_current_sha256=expected_existing,
        expected_new_sha256=expected_candidate,
        rollback_source=backup_result.backup_path,
        error_type=SarooDeploymentApplyError,
    )

    return SarooDeploymentApplyResult(
        card_root=plan.card_root,
        destination_path=destination,
        backup_path=backup_result.backup_path,
        previous_sha256=expected_existing,
        candidate_sha256=expected_candidate,
        backup_reused=backup_result.backup_reused,
    )


def restore_saroo_firmware(
    card_root: os.PathLike[str] | str,
    backup_firmware: os.PathLike[str] | str,
    *,
    expected_current_sha256: str,
    expected_backup_sha256: str,
    archive_root: os.PathLike[str] | str | None = None,
) -> SarooDeploymentRestoreResult:
    """Restore a verified off-card baseline to modern ``SAROO/ssfirm.bin``.

    Before restore, the current card firmware is itself preserved off-card so a
    restore operation never destroys the only copy of the currently installed
    candidate.
    """

    current_expected = _validated_sha256(
        expected_current_sha256,
        label="expected current firmware hash",
        error_type=SarooDeploymentRestoreError,
    )
    backup_expected = _validated_sha256(
        expected_backup_sha256,
        label="expected backup firmware hash",
        error_type=SarooDeploymentRestoreError,
    )

    card = _canonical(card_root)
    backup = _canonical(backup_firmware)
    if not backup.is_file():
        raise SarooDeploymentRestoreError(f"backup firmware is not a file: {backup}")
    if _inside(backup, card):
        raise SarooDeploymentRestoreError("restore backup must be outside the mounted SAROO card")
    if _hash_file(backup, error_type=SarooDeploymentRestoreError) != backup_expected:
        raise SarooDeploymentRestoreError("backup firmware hash does not match the reviewed value")

    report = inspect_saroo_sd_layout(card)
    if report.layout != SAROO_SD_LAYOUT_MODERN or len(report.firmware_files) != 1:
        raise SarooDeploymentRestoreError(
            "restore is gated to exactly one modern SAROO/ssfirm.bin firmware file"
        )
    current = report.firmware_files[0]
    if current.sha256 != current_expected:
        raise SarooDeploymentRestoreError(
            "current card firmware hash does not match the reviewed restore state"
        )
    if current.sha256 == backup_expected:
        raise SarooDeploymentRestoreError("card already contains the requested backup firmware")

    destination = _firmware_destination(
        card,
        current.relative_path,
        error_type=SarooDeploymentRestoreError,
    )
    archives = _canonical(archive_root) if archive_root is not None else backup.parent
    if _inside(archives, card):
        raise SarooDeploymentRestoreError("pre-restore archive root must be outside the card")
    archive_path = archives / f"ssfirm_pre_restore_{current.sha256[:16]}.bin"
    archive_reused = _copy_new_verified(
        destination,
        archive_path,
        current_expected,
        error_type=SarooDeploymentRestoreError,
    )

    _replace_verified(
        backup,
        destination,
        expected_current_sha256=current_expected,
        expected_new_sha256=backup_expected,
        rollback_source=archive_path,
        error_type=SarooDeploymentRestoreError,
    )

    return SarooDeploymentRestoreResult(
        card_root=card,
        destination_path=destination,
        backup_path=backup,
        pre_restore_archive_path=archive_path,
        replaced_sha256=current_expected,
        restored_sha256=backup_expected,
        archive_reused=archive_reused,
    )
