"""Explicit whole-card-guarded SAROO Saturn-firmware apply command."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_backup_directory
from rikai_kotoba.hardware.saturn.saroo.guarded_deployment import (
    apply_saroo_firmware_guarded,
)


_CONFIRM_TEXT = "APPLY-SSFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-apply",
        description=(
            "Explicitly replace modern SAROO/ssfirm.bin only after verifying the "
            "reviewed whole-card inventory and off-card firmware backup."
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
    if not args.guard_manifest or not args.expected_guard_manifest_sha256:
        print(
            "srk-saroo-apply: --guard-manifest and "
            "--expected-guard-manifest-sha256 are required for every card write",
            file=sys.stderr,
        )
        return 2

    backup_root = args.backup_root or str(default_saroo_backup_directory())
    try:
        guarded = apply_saroo_firmware_guarded(
            args.card_root,
            args.candidate,
            backup_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            expected_existing_sha256=args.expected_existing_sha256,
            expected_candidate_sha256=args.expected_candidate_sha256,
        )
    except Exception as exc:
        print(f"srk-saroo-apply: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    result = guarded.deployment
    print("SAROO Saturn-firmware guarded apply complete")
    print("-" * 48)
    print(f"Card root        : {result.card_root}")
    print(f"Guard manifest   : {guarded.guard_manifest_path}")
    print(f"Guard SHA-256    : {guarded.guard_manifest_sha256}")
    print("Pre-write guard  : MATCH")
    print("Post-write guard : MATCH (only SAROO/ssfirm.bin authorised to differ)")
    print(f"Destination      : {result.destination_path}")
    print(f"Verified backup  : {result.backup_path}")
    print(
        "Backup action    : "
        + ("reused existing verified backup" if result.backup_reused else "created and verified")
    )
    print(f"Previous SHA-256 : {result.previous_sha256}")
    print(f"Installed SHA-256: {result.candidate_sha256}")
    print()
    print("Only SAROO/ssfirm.bin was authorised to change.")
    print("MCU/FPGA firmware, configuration, directories, and game-library inventory matched.")
    print("Keep the verified baseline backup and guard manifest for restore.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
