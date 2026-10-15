"""Validate and optionally deploy the real Space Spectre SBL/GM candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_gm_hardware_gate import (
    CONFIRMATION_TOKEN,
    DEFAULT_DESTINATION_NAME,
    run_saturn_sbl_gm_hardware_gate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-hardware",
        description=(
            "Revalidate the successful Space Spectre Sega SDDRV/Direct-MIDI GM "
            "candidate and optionally deploy exactly one fresh CUE/BIN directory "
            "to an existing SAROO/ISO category under a whole-card guard."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--card-root", required=True, type=Path)
    parser.add_argument("--category", default="TEST")
    parser.add_argument("--name", default=DEFAULT_DESTINATION_NAME)
    parser.add_argument("--guard-manifest", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="After all read-only gates pass, write exactly one fresh SAROO directory",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply; must be exactly {CONFIRMATION_TOKEN}",
    )
    return parser


def _guard_path(args) -> Path:
    if args.guard_manifest is not None:
        return args.guard_manifest.expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return (
        args.workspace.expanduser()
        / "Backups"
        / "SAROO"
        / f"card_before_space_spectre_sbl_gm_{stamp}.json"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    guard_manifest = _guard_path(args)

    try:
        result = run_saturn_sbl_gm_hardware_gate(
            args.project,
            args.card_root,
            guard_manifest,
            destination_name=args.name,
            category=args.category,
            apply=args.apply,
            confirmation=args.confirm,
        )
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-hardware: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    evidence = result.evidence
    plan = evidence.plan
    print("SRK Space Spectre / Sega Direct MIDI / hardware gate")
    print("-----------------------------------------------------")
    print(f"Project              : {evidence.project_root}")
    print(f"Manifest SHA-256     : {evidence.manifest_sha256}")
    print(f"Build report SHA-256 : {evidence.report_sha256}")
    print(f"Melodic bank SHA-256 : {evidence.melodic_bank_sha256}")
    print(f"Drum bank SHA-256    : {evidence.drum_bank_sha256}")
    print(f"Sound driver SHA-256 : {evidence.sound_driver_sha256}")
    print(f"sega_snd.a SHA-256   : {evidence.sega_sound_library_sha256}")
    print(f"Destination          : {plan.destination_directory}")
    print(f"BIN SHA-256          : {plan.bin_sha256}")
    print(f"CUE SHA-256          : {plan.cue_sha256}")
    print(f"MODE1 sectors        : {plan.sector_count}")
    print(f"Raw bytes            : {plan.raw_bytes}")

    if not result.applied:
        print()
        print("Result               : READ-ONLY HARDWARE GATE READY")
        print("SAROO writes         : NONE")
        print("Whole-card guard     : not created (no write requested)")
        print(f"Apply token          : {CONFIRMATION_TOKEN}")
        return 0

    assert result.guard is not None
    assert result.deployment is not None
    assert result.verification is not None
    print(f"Guard manifest       : {result.guard.manifest_path}")
    print(f"Guard SHA-256        : {result.guard.manifest_sha256}")
    print(f"Destination BIN      : {result.deployment.destination_bin}")
    print(f"Destination CUE      : {result.deployment.destination_cue}")
    print(f"Card files           : {result.verification.file_count}")
    print(f"Card directories     : {result.verification.directory_count}")
    print(f"Card bytes           : {result.verification.total_file_bytes}")
    print(f"Card files hashed    : {result.verification.hashed_file_count}")
    print("Whole-card result    : MATCH")
    print()
    print("Result               : VERIFIED AND SAFE TO EJECT")
    print("Only the new Space Spectre test directory and its verified BIN/CUE may differ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
