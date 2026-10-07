"""Read-only developer-facing SAROO Saturn-firmware deployment planner."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_backup_directory
from rikai_kotoba.hardware.saturn.saroo import plan_saroo_firmware_deployment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-deployment",
        description=(
            "Compare a built Saturn-side SAROO firmware with the firmware on a "
            "mounted card and print a preserve-first deployment plan. This "
            "command is read-only: it does not create backups or modify the card."
        ),
    )
    parser.add_argument(
        "card_root",
        help="Root directory of the mounted SAROO SD card",
    )
    parser.add_argument(
        "candidate",
        help="Built candidate ssfirm.bin outside the mounted SD card",
    )
    parser.add_argument(
        "--backup-root",
        default=None,
        help=(
            "Off-card directory proposed for the existing-firmware backup; "
            "defaults to SRK-Workspace/Backups/SAROO"
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    backup_root = args.backup_root or str(default_saroo_backup_directory())

    try:
        plan = plan_saroo_firmware_deployment(
            args.card_root,
            args.candidate,
            backup_root,
        )
    except Exception as exc:
        print(f"srk-saroo-deployment: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SAROO Saturn-firmware deployment plan")
    print("-" * 44)
    print(f"Card root       : {plan.card_root}")
    print(f"Card layout     : {plan.layout}")
    print("Access policy   : READ-ONLY PLAN; no files will be modified")
    print()

    if plan.existing_firmware is not None:
        current = plan.existing_firmware
        print("Existing card firmware (independent baseline):")
        print(f"  Path     : {current.relative_path}")
        print(f"  Size     : {current.size} bytes")
        print(f"  SHA-256  : {current.sha256}")
    else:
        print("Existing card firmware: [not uniquely identified]")

    print()
    print("Candidate firmware:")
    print(f"  Path     : {plan.candidate.path}")
    print(f"  Size     : {plan.candidate.size} bytes")
    print(f"  SHA-256  : {plan.candidate.sha256}")

    print()
    if plan.destination_relative_path is not None:
        print(f"Future destination : {plan.destination_relative_path}")
    else:
        print("Future destination : [not authorised]")
    if plan.backup_path is not None:
        print(f"Proposed backup    : {plan.backup_path}")
        print(
            "Backup status      : "
            + ("already verified" if plan.backup_already_valid else "not created")
        )
    else:
        print("Proposed backup    : [not authorised]")

    print(
        "Replacement needed : "
        + ("yes" if plan.replacement_needed else "no; files are byte-identical")
    )
    print(
        "Future apply gate  : "
        + ("READY FOR EXPLICIT APPLY DESIGN" if plan.ready_for_future_apply else "BLOCKED")
    )

    if plan.warnings:
        print()
        print("Warnings:")
        for warning in plan.warnings:
            print(f"  - {warning}")

    print()
    print("No backup was created. No SD-card file was modified.")
    return 0 if plan.ready_for_future_apply or not plan.replacement_needed else 2


if __name__ == "__main__":
    raise SystemExit(main())
