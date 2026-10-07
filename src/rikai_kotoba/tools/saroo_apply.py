"""Explicit backup-first SAROO Saturn-firmware apply command."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_backup_directory
from rikai_kotoba.hardware.saturn.saroo import apply_saroo_firmware


_CONFIRM_TEXT = "APPLY-SSFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-apply",
        description=(
            "Explicitly replace modern SAROO/ssfirm.bin only after "
            "creating and SHA-256-verifying an off-card backup."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument("candidate", help="Built candidate ssfirm.bin outside the card")
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
    parser.add_argument(
        "--expected-candidate-sha256",
        required=True,
        help="Full SHA-256 of the candidate firmware from the reviewed plan",
    )
    parser.add_argument(
        "--confirm-write",
        required=True,
        metavar=_CONFIRM_TEXT,
        help=f"Required explicit confirmation token: {_CONFIRM_TEXT}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.confirm_write != _CONFIRM_TEXT:
        print(
            f"srk-saroo-apply: confirmation token must be exactly {_CONFIRM_TEXT}",
            file=sys.stderr,
        )
        return 2

    backup_root = args.backup_root or str(default_saroo_backup_directory())
    try:
        result = apply_saroo_firmware(
            args.card_root,
            args.candidate,
            backup_root,
            expected_existing_sha256=args.expected_existing_sha256,
            expected_candidate_sha256=args.expected_candidate_sha256,
        )
    except Exception as exc:
        print(f"srk-saroo-apply: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SAROO Saturn-firmware apply complete")
    print("-" * 44)
    print(f"Card root        : {result.card_root}")
    print(f"Destination      : {result.destination_path}")
    print(f"Verified backup  : {result.backup_path}")
    print(
        "Backup action    : "
        + ("reused existing verified backup" if result.backup_reused else "created and verified")
    )
    print(f"Previous SHA-256 : {result.previous_sha256}")
    print(f"Installed SHA-256: {result.candidate_sha256}")
    print()
    print("Only SAROO/ssfirm.bin was replaced. MCU/FPGA firmware was not touched.")
    print("Keep the verified backup for restore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
