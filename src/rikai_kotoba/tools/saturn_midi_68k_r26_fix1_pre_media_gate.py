"""CLI for independent read-only R26 Space Spectre FIX1 pre-media review."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r26_fix1_pre_media_gate import (
    inspect_saturn_midi_68k_r26_fix1_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r26-space-spectre-fix1-pre-media-gate",
        description=(
            "Revalidate the Eridu-accepted Space Spectre FIX1 candidate and "
            "produce only a read-only fresh SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_saturn_midi_68k_r26_fix1_pre_media(
            args.project,
            args.repository_root,
            args.card_root,
            destination_name=args.name,
            category=args.category,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r26-space-spectre-fix1-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    print("SRK R26 Space Spectre FIX1 pre-media gate")
    print("-----------------------------------------")
    print(f"Project                    : {result.project_root}")
    print(f"Accepted R24 baseline      : {result.baseline_root}")
    print(f"Manifest SHA-256           : {result.manifest_sha256}")
    print(f"Build report SHA-256       : {result.report_sha256}")
    print(f"FIX1 resident image SHA-256: {result.resident_image_sha256}")
    print(f"FIX1 resident source SHA   : {result.resident_source_sha256}")
    print(f"FIX1 resident header SHA   : {result.resident_header_sha256}")
    print(f"Candidate main SHA-256     : {result.candidate_main_sha256}")
    print(f"Runtime after SHA-256      : {result.runtime_after_sha256}")
    print(f"Deployable BIN SHA-256     : {result.deployable_bin_sha256}")
    print(f"Deployable CUE SHA-256     : {result.deployable_cue_sha256}")
    print("Records / batches          : 9154 / 287")
    print("Note On / Note Off         : 4381 / 4381")
    print("Raw peak / release steals  : 10 / 12")
    print("Busy / dropped Note Ons    : 0")
    print("Success text policy        : PASS ONLY IN PHASE 5")
    print("Provisional RR             : 16 (production RR UNSET)")
    print()
    print("Read-only SAROO plan")
    print(f"Card root                  : {plan.card_root}")
    if plan.category_directory is not None:
        print(f"Category                   : {plan.category_directory.name}")
    else:
        print("Category                   : none")
    print(f"Destination                : {plan.destination_directory}")
    print(f"BIN size                   : {plan.bin_size} bytes")
    print(f"CUE size                   : {plan.cue_size} bytes")
    print(f"MODE1 sectors              : {result.sector_count}")
    print("Fresh MODE1 verification   : PASS")
    print("Eridu FIX1 anchors         : PASS")
    print("SAROO destination          : FRESH")
    print("SAROO writes               : NONE")
    print()
    print("Result                     : R26 FIX1 PRE-MEDIA GATE PASS")
    print("No SD-card files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
