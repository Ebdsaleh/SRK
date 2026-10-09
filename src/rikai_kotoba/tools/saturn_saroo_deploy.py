"""Plan or apply guarded deployment of a verified Saturn CUE/BIN image to SAROO."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN,
    DEFAULT_DESTINATION_NAME,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-saroo-deploy",
        description=(
            "Safely deploy one SRK-verified standalone Saturn MODE1/2352 CUE/BIN "
            "pair into a new SAROO/ISO game directory. The default action is read-only planning."
        ),
    )
    parser.add_argument("--card-root", required=True, help="Mounted SAROO SD-card root")
    parser.add_argument("--project", required=True, help="Successful SRK standalone project directory")
    parser.add_argument(
        "--name",
        default=DEFAULT_DESTINATION_NAME,
        help=f"New game directory name (default: {DEFAULT_DESTINATION_NAME})",
    )
    parser.add_argument(
        "--category",
        default=None,
        help=(
            "Existing direct child of SAROO/ISO in which to place the new game directory; "
            "SRK never creates a category implicitly"
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the guarded copy after all validation gates pass",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply; must be exactly {CONFIRMATION_TOKEN}",
    )
    return parser


def _print_plan(plan) -> None:
    print("SRK standalone Saturn SAROO deployment plan")
    print("--------------------------------------------")
    print(f"Card root       : {plan.card_root}")
    print(f"Project         : {plan.project_root}")
    if plan.category_directory is not None:
        print(f"Category        : {plan.category_directory.name}")
    else:
        print("Category        : none (directly beneath SAROO/ISO)")
    print(f"Destination     : {plan.destination_directory}")
    print(f"Source BIN      : {plan.source_bin}")
    print(f"  Size          : {plan.bin_size} bytes")
    print(f"  SHA-256       : {plan.bin_sha256}")
    print(f"Source CUE      : {plan.source_cue}")
    print(f"  Size          : {plan.cue_size} bytes")
    print(f"  SHA-256       : {plan.cue_sha256}")
    print(f"Mode 1 sectors  : {plan.sector_count}")
    print(f"Raw track bytes : {plan.raw_bytes}")
    print("Fresh verification: MODE1/2352 BIN matches the intermediate ISO.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if not args.apply:
            plan = plan_saroo_standalone_image_deployment(
                args.card_root,
                args.project,
                destination_name=args.name,
                category=args.category,
            )
            _print_plan(plan)
            print()
            print("Access policy: READ-ONLY PLAN; no SD-card files were modified.")
            print("To apply this exact class of operation, rerun with:")
            print(f"  --apply --confirm {CONFIRMATION_TOKEN}")
            return 0

        result = apply_saroo_standalone_image_deployment(
            args.card_root,
            args.project,
            destination_name=args.name,
            category=args.category,
            confirmation=args.confirm,
        )
        _print_plan(result.plan)
        print()
        print("Deployment result: VERIFIED")
        print(f"Destination BIN : {result.destination_bin}")
        print(f"  SHA-256       : {result.bin_sha256}")
        print(f"Destination CUE : {result.destination_cue}")
        print(f"  SHA-256       : {result.cue_sha256}")
        print("Existing SAROO game directories were not overwritten or removed.")
        print("Safely eject the SD card before moving it to Saturn hardware.")
        return 0
    except Exception as exc:
        print(
            f"srk-saturn-saroo-deploy: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
