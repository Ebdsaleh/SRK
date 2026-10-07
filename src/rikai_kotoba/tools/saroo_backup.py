"""Create a verified off-card backup of current SAROO Saturn firmware."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_backup_directory
from rikai_kotoba.hardware.saturn.saroo import backup_saroo_firmware


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-backup",
        description=(
            "Copy the current modern SAROO/ssfirm.bin to a verified off-card "
            "content-addressed backup without modifying the SD card."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument(
        "--backup-root",
        default=None,
        help="Off-card backup directory; defaults to SRK-Workspace/Backups/SAROO",
    )
    parser.add_argument(
        "--expected-existing-sha256",
        required=True,
        help="Full SHA-256 of the existing card firmware from the reviewed plan",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    backup_root = args.backup_root or str(default_saroo_backup_directory())

    try:
        result = backup_saroo_firmware(
            args.card_root,
            backup_root,
            expected_existing_sha256=args.expected_existing_sha256,
        )
    except Exception as exc:
        print(f"srk-saroo-backup: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SAROO Saturn-firmware baseline backup complete")
    print("-" * 48)
    print(f"Card root       : {result.card_root}")
    print(f"Source firmware : {result.source_path}")
    print(f"Verified backup : {result.backup_path}")
    print(f"SHA-256         : {result.firmware_sha256}")
    print(
        "Backup action    : "
        + ("reused existing verified backup" if result.backup_reused else "created and verified")
    )
    print()
    print("The SAROO SD card was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
