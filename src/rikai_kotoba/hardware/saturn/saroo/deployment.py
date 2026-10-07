"""Read-only planning for safe SAROO Saturn-firmware replacement.

The user's existing SAROO SD card is treated as independent known-good evidence.
SRK does not assume that its current firmware came from the same upstream source
revision used for an SRK build.  This module therefore compares hashes and plans
an off-card backup before any later deployment action can be considered.

Planning is intentionally read-only: it never creates a backup, writes to the
card, replaces firmware, or creates directories.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os

from .sd_layout import (
    SAROO_SD_LAYOUT_MODERN,
    SarooSdFileInfo,
    inspect_saroo_sd_layout,
)


class SarooDeploymentPlanError(RuntimeError):
    """Raised when a safe read-only deployment plan cannot be produced."""


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


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _hash_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise SarooDeploymentPlanError(f"cannot read file {path}: {exc}") from exc
    return digest.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def plan_saroo_firmware_deployment(
    card_root: os.PathLike[str] | str,
    candidate_firmware: os.PathLike[str] | str,
    backup_root: os.PathLike[str] | str,
) -> SarooDeploymentPlan:
    """Describe a future SAROO Saturn-firmware replacement without writing.

    Only an unambiguous modern card layout (``SAROO/ssfirm.bin``) is eligible
    for a future apply operation.  Legacy, mixed, or unrecognised layouts are
    reported but never guessed through.

    The candidate and backup location must both be outside the mounted card.
    The proposed backup filename is content-addressed from the existing card
    firmware hash so repeated planning remains deterministic.
    """

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
