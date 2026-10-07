"""Create and verify off-card SAROO SD-card inventory manifests."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SAROO_CARD_INVENTORY_HASH_MAX_BYTES,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-card-guard",
        description=(
            "Create or verify an off-card inventory of a mounted SAROO SD card. "
            "The card itself is never modified."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser(
        "snapshot",
        help="Create a new off-card baseline inventory manifest",
    )
    snapshot.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    snapshot.add_argument("manifest", help="New manifest path outside the mounted card")
    snapshot.add_argument(
        "--hash-max-bytes",
        type=int,
        default=SAROO_CARD_INVENTORY_HASH_MAX_BYTES,
        help=(
            "Hash ordinary files up to this size; all paths and file sizes are always "
            "recorded (default: 1048576 bytes)"
        ),
    )

    verify = subparsers.add_parser(
        "verify",
        help="Verify the mounted card against an existing off-card manifest",
    )
    verify.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    verify.add_argument("manifest", help="Existing off-card inventory manifest")
    verify.add_argument(
        "--allow-changed-path",
        action="append",
        default=[],
        help="Allow exactly this relative path to differ; may be repeated",
    )
    return parser


def _print_bytes(value: int) -> str:
    gib = value / (1024 ** 3)
    return f"{value} bytes ({gib:.2f} GiB)"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "snapshot":
            result = create_saroo_card_inventory(
                args.card_root,
                args.manifest,
                hash_max_bytes=args.hash_max_bytes,
            )
            print("SAROO SD-card guard baseline created")
            print("-" * 44)
            print(f"Card root       : {result.card_root}")
            print(f"Manifest        : {result.manifest_path}")
            print(f"Files           : {result.file_count}")
            print(f"Directories     : {result.directory_count}")
            print(f"Total file bytes: {_print_bytes(result.total_file_bytes)}")
            print(f"Files SHA-256ed : {result.hashed_file_count}")
            print(f"Manifest SHA-256: {result.manifest_sha256}")
            print()
            print("The SAROO SD card was not modified.")
            return 0

        verification = verify_saroo_card_inventory(
            args.card_root,
            args.manifest,
            allowed_changed_paths=args.allow_changed_path,
        )
        print("SAROO SD-card guard verification")
        print("-" * 44)
        print(f"Card root       : {verification.card_root}")
        print(f"Manifest        : {verification.manifest_path}")
        print(f"Files           : {verification.file_count}")
        print(f"Directories     : {verification.directory_count}")
        print(f"Total file bytes: {_print_bytes(verification.total_file_bytes)}")
        print(f"Files SHA-256ed : {verification.hashed_file_count}")
        print(f"Result          : {'MATCH' if verification.valid else 'DIFFERENCES FOUND'}")
        if verification.differences:
            print()
            print("Differences:")
            for difference in verification.differences[:50]:
                print(f"  - {difference}")
            if len(verification.differences) > 50:
                print(f"  - ... {len(verification.differences) - 50} more")
        print()
        print("The SAROO SD card was not modified.")
        return 0 if verification.valid else 2
    except Exception as exc:
        print(f"srk-saroo-card-guard: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
