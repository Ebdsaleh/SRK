"""CLI for read-only R26 Space Spectre FIX1 whole-card guard preparation."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r26_fix1_guard_prepare import (
    prepare_saturn_midi_68k_r26_space_spectre_fix1_guard,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r26-space-spectre-fix1-guard-prepare",
        description=(
            "Revalidate FIX1, create and verify a complete off-card SAROO "
            "inventory, and publish an off-card preparation receipt. "
            "This command performs no card deployment."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_saturn_midi_68k_r26_space_spectre_fix1_guard(
            args.project,
            args.repository_root,
            args.card_root,
            args.guard_manifest,
            args.receipt,
            destination_name=args.name,
            category=args.category,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r26-space-spectre-fix1-guard-prepare: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    pre = result.pre_media
    inv = result.guard_inventory
    print("SRK R26 Space Spectre FIX1 whole-card guard PREPARE")
    print("---------------------------------------------------")
    print(f"Project                    : {pre.project_root}")
    print(f"Candidate manifest SHA-256 : {pre.manifest_sha256}")
    print(f"Build report SHA-256       : {pre.report_sha256}")
    print(f"FIX1 resident image SHA-256: {pre.resident_image_sha256}")
    print(f"Candidate main SHA-256     : {pre.candidate_main_sha256}")
    print(f"Runtime after SHA-256      : {pre.runtime_after_sha256}")
    print(f"Accepted BIN SHA-256       : {pre.deployable_bin_sha256}")
    print(f"Accepted CUE SHA-256       : {pre.deployable_cue_sha256}")
    print(f"Future destination         : {pre.plan.destination_directory}")
    print()
    print("Whole-card guard")
    print(f"Card root                  : {inv.card_root}")
    print(f"Guard manifest             : {inv.manifest_path}")
    print(f"Guard manifest SHA-256     : {inv.manifest_sha256}")
    print(f"Card files                 : {inv.file_count}")
    print(f"Card directories           : {inv.directory_count}")
    print(f"Total file bytes           : {inv.total_file_bytes}")
    print(f"Files SHA-256ed            : {inv.hashed_file_count}")
    print("Exact final guard          : MATCH")
    print()
    print("Bound FIX1 preparation receipt")
    print(f"Receipt                    : {result.receipt_path}")
    print(f"Receipt SHA-256            : {result.receipt_sha256}")
    print("Candidate/card binding     : PASS")
    print("Destination freshness      : PASS")
    print("SAROO writes               : NONE")
    print("Apply path in this command : NONE")
    print()
    print("Result                     : R26 SPACE SPECTRE FIX1 PREPARE PASS")
    print("Both guard files were created off-card. No SD-card file was modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
