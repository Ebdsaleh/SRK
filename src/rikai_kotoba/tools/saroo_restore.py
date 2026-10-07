"""Explicit whole-card-guarded restore for SAROO Saturn-side firmware."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.guarded_deployment import (
    restore_saroo_firmware_guarded,
)


_CONFIRM_TEXT = "RESTORE-SSFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-restore",
        description=(
            "Restore a verified off-card SAROO ssfirm.bin baseline while requiring "
            "the reviewed whole-card inventory to remain intact."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument("backup", help="Verified off-card baseline ssfirm backup")
    parser.add_argument(
        "--guard-manifest",
        default=None,
        help="Reviewed off-card whole-card inventory manifest",
    )
    parser.add_argument(
        "--expected-guard-manifest-sha256",
        default=None,
        help="Full reviewed SHA-256 printed when the guard manifest was created",
    )
    parser.add_argument(
        "--expected-current-sha256",
        required=True,
        help="Full SHA-256 of the firmware currently expected on the card",
    )
    parser.add_argument(
        "--expected-backup-sha256",
        required=True,
        help="Full SHA-256 of the backup that will be restored",
    )
    parser.add_argument(
        "--archive-root",
        default=None,
        help="Optional off-card directory for preserving the current firmware before restore",
    )
    parser.add_argument(
        "--confirm-restore",
        required=True,
        metavar=_CONFIRM_TEXT,
        help=f"Required explicit confirmation token: {_CONFIRM_TEXT}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.confirm_restore != _CONFIRM_TEXT:
        print(
            f"srk-saroo-restore: confirmation token must be exactly {_CONFIRM_TEXT}",
            file=sys.stderr,
        )
        return 2
    if not args.guard_manifest or not args.expected_guard_manifest_sha256:
        print(
            "srk-saroo-restore: --guard-manifest and "
            "--expected-guard-manifest-sha256 are required for every card write",
            file=sys.stderr,
        )
        return 2

    try:
        guarded = restore_saroo_firmware_guarded(
            args.card_root,
            args.backup,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            expected_current_sha256=args.expected_current_sha256,
            expected_backup_sha256=args.expected_backup_sha256,
            archive_root=args.archive_root,
        )
    except Exception as exc:
        print(f"srk-saroo-restore: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    result = guarded.deployment
    print("SAROO Saturn-firmware guarded restore complete")
    print("-" * 48)
    print(f"Card root           : {result.card_root}")
    print(f"Guard manifest      : {guarded.guard_manifest_path}")
    print(f"Guard SHA-256       : {guarded.guard_manifest_sha256}")
    print("Pre-restore guard   : MATCH (only SAROO/ssfirm.bin authorised to differ)")
    print("Post-restore guard  : MATCH (exact original card inventory restored)")
    print(f"Destination         : {result.destination_path}")
    print(f"Restored from       : {result.backup_path}")
    print(f"Pre-restore archive : {result.pre_restore_archive_path}")
    print(
        "Archive action      : "
        + ("reused existing verified archive" if result.archive_reused else "created and verified")
    )
    print(f"Replaced SHA-256    : {result.replaced_sha256}")
    print(f"Restored SHA-256    : {result.restored_sha256}")
    print()
    print("Only SAROO/ssfirm.bin was authorised to change.")
    print("MCU/FPGA firmware, configuration, directories, and game-library inventory matched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
