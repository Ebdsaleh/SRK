"""Explicit whole-card-guarded transition between accepted SAROO firmware builds."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_backup_directory
from rikai_kotoba.hardware.saturn.saroo.firmware_transition import (
    transition_saroo_firmware_guarded,
)


_CONFIRM_TEXT = "TRANSITION-SSFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-transition",
        description=(
            "Replace an already accepted SRK SAROO ssfirm.bin with a new research "
            "build while preserving the current firmware and requiring the reviewed "
            "whole-card inventory to match everywhere except the firmware, SRK's "
            "validated capture outputs, and an optional exact reviewed SS_SAVE.BIN state."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument("candidate", help="New built candidate ssfirm.bin outside the card")
    parser.add_argument(
        "--backup-root",
        default=None,
        help="Off-card backup directory; defaults to SRK-Workspace/Backups/SAROO",
    )
    parser.add_argument(
        "--guard-manifest",
        required=True,
        help="Reviewed off-card whole-card inventory manifest",
    )
    parser.add_argument(
        "--expected-guard-manifest-sha256",
        required=True,
        help="Full reviewed SHA-256 printed when the guard manifest was created",
    )
    parser.add_argument(
        "--expected-current-sha256",
        required=True,
        help="Full SHA-256 of the currently accepted firmware installed on the card",
    )
    parser.add_argument(
        "--expected-candidate-sha256",
        required=True,
        help="Full SHA-256 of the new candidate firmware",
    )
    parser.add_argument(
        "--expected-ss-save-sha256",
        default=None,
        help=(
            "Optional full SHA-256 of the exact reviewed SAROO/SS_SAVE.BIN state. "
            "Requires --expected-ss-save-size and causes that save state to be "
            "preserved off-card and required unchanged through the transition."
        ),
    )
    parser.add_argument(
        "--expected-ss-save-size",
        type=int,
        default=None,
        help=(
            "Optional exact byte size of the reviewed SAROO/SS_SAVE.BIN state. "
            "Requires --expected-ss-save-sha256."
        ),
    )
    parser.add_argument(
        "--confirm-transition",
        required=True,
        metavar=_CONFIRM_TEXT,
        help=f"Required explicit confirmation token: {_CONFIRM_TEXT}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.confirm_transition != _CONFIRM_TEXT:
        print(
            f"srk-saroo-transition: confirmation token must be exactly {_CONFIRM_TEXT}",
            file=sys.stderr,
        )
        return 2

    if (args.expected_ss_save_sha256 is None) != (args.expected_ss_save_size is None):
        print(
            "srk-saroo-transition: reviewed SS_SAVE.BIN requires both "
            "--expected-ss-save-sha256 and --expected-ss-save-size",
            file=sys.stderr,
        )
        return 2

    backup_root = args.backup_root or str(default_saroo_backup_directory())
    try:
        guarded = transition_saroo_firmware_guarded(
            args.card_root,
            args.candidate,
            backup_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            expected_current_sha256=args.expected_current_sha256,
            expected_candidate_sha256=args.expected_candidate_sha256,
            expected_ss_save_sha256=args.expected_ss_save_sha256,
            expected_ss_save_size=args.expected_ss_save_size,
        )
    except Exception as exc:
        print(f"srk-saroo-transition: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    result = guarded.deployment
    print("SAROO Saturn-firmware guarded transition complete")
    print("-" * 52)
    print(f"Card root          : {result.card_root}")
    print(f"Guard manifest     : {guarded.guard_manifest_path}")
    print(f"Guard SHA-256      : {guarded.guard_manifest_sha256}")
    if guarded.reviewed_save_path is None:
        print("Pre-transition guard : MATCH (firmware / validated SRK capture outputs may differ)")
        print("Post-transition guard: MATCH (same narrow research-output allowance)")
    else:
        print(
            "Pre-transition guard : MATCH (firmware / validated SRK captures / exact reviewed save may differ)"
        )
        print("Post-transition guard: MATCH (same exact reviewed-save allowance)")
    print(f"Destination        : {result.destination_path}")
    print(f"Preserved previous : {result.backup_path}")
    print(
        "Backup action      : "
        + ("reused existing verified backup" if result.backup_reused else "created and verified")
    )
    print(f"Previous SHA-256   : {result.previous_sha256}")
    print(f"Installed SHA-256  : {result.candidate_sha256}")
    if guarded.reviewed_save_path is not None:
        print()
        print(f"Reviewed SS_SAVE   : {guarded.reviewed_save_path}")
        print(f"SS_SAVE size       : {guarded.reviewed_save_size} bytes")
        print(f"SS_SAVE SHA-256    : {guarded.reviewed_save_sha256}")
        print(f"Preserved SS_SAVE  : {guarded.reviewed_save_backup_path}")
        print(
            "Save backup action : "
            + (
                "reused existing verified backup"
                if guarded.reviewed_save_backup_reused
                else "created and verified"
            )
        )
    print()
    print("Only SAROO/ssfirm.bin was replaced by this transition.")
    print("Any present SRK_WRAML.BIN / SRK_WRAMH.BIN remained exact 1 MiB research outputs.")
    if guarded.reviewed_save_path is not None:
        print("The exact reviewed SAROO/SS_SAVE.BIN state was preserved off-card and remained unchanged.")
    print("Games, configuration, MCU/FPGA firmware, and unrelated card paths matched.")
    print("Keep accepted firmware/save backups and the original guard manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
