"""Explicit verified restore for SAROO Saturn-side firmware."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo import restore_saroo_firmware


_CONFIRM_TEXT = "RESTORE-SSFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-restore",
        description=(
            "Restore a verified off-card SAROO ssfirm.bin baseline. The current "
            "card firmware is preserved off-card before restore."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument("backup", help="Verified off-card baseline ssfirm backup")
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

    try:
        result = restore_saroo_firmware(
            args.card_root,
            args.backup,
            expected_current_sha256=args.expected_current_sha256,
            expected_backup_sha256=args.expected_backup_sha256,
            archive_root=args.archive_root,
        )
    except Exception as exc:
        print(f"srk-saroo-restore: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SAROO Saturn-firmware restore complete")
    print("-" * 44)
    print(f"Card root           : {result.card_root}")
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
    print("Only SAROO/ssfirm.bin was restored. MCU/FPGA firmware was not touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
