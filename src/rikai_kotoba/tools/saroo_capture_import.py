"""Import real-hardware SAROO Work RAM capture files into SRK storage."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.application.paths import default_saroo_dump_directory
from rikai_kotoba.hardware.saturn.saroo.capture_ingest import (
    import_saroo_game_work_ram_high_capture,
    import_saroo_work_ram_captures,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-capture-import",
        description=(
            "Read SRK Work RAM capture files from a mounted SAROO card and publish "
            "a verified immutable capture artifact outside the card."
        ),
    )
    parser.add_argument("card_root", help="Root directory of the mounted SAROO SD card")
    parser.add_argument(
        "--store-root",
        default=None,
        help="Off-card capture root; defaults to SRK-Workspace/Dumps/SAROO",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Title-neutral checkpoint label stored in the capture manifest",
    )
    parser.add_argument(
        "--session-label",
        default="real-hardware",
        help="Optional session label stored in the capture manifest",
    )
    parser.add_argument(
        "--game-wramh",
        action="store_true",
        help="Import only SAROO/SRK_GAME_WRAMH.BIN as an in-game WRAM-H capture",
    )
    return parser


def _format_address(value: int | None) -> str:
    return "none" if value is None else f"0x{value:08X}"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store_root = args.store_root or str(default_saroo_dump_directory())

    try:
        if args.game_wramh:
            result = import_saroo_game_work_ram_high_capture(
                args.card_root,
                store_root,
                checkpoint=args.checkpoint or "saroo-ingame",
                session_label=args.session_label,
            )
        else:
            result = import_saroo_work_ram_captures(
                args.card_root,
                store_root,
                checkpoint=args.checkpoint or "saroo-menu",
                session_label=args.session_label,
            )
    except Exception as exc:
        print(f"srk-saroo-capture-import: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK SAROO real-hardware capture import complete")
    print("-" * 52)
    print(f"Card root        : {result.card_root}")
    print(f"Capture artifact : {result.artifact.directory}")
    print(f"Manifest         : {result.artifact.manifest_path}")
    print()
    for summary in result.summaries:
        print(summary.relative_path)
        print(f"  Saturn range   : 0x{summary.memory_range.start_address:08X}-0x{summary.memory_range.end_address_exclusive - 1:08X}")
        print(f"  Size           : {summary.size} bytes")
        print(f"  SHA-256        : {summary.sha256}")
        print(f"  Non-zero bytes : {summary.nonzero_bytes}")
        print(f"  Zero bytes     : {summary.zero_bytes}")
        print(f"  First non-zero : {_format_address(summary.first_nonzero_address)}")
        print(f"  Last non-zero  : {_format_address(summary.last_nonzero_address)}")
    print()
    print("The mounted SAROO SD card was read only and was not modified.")
    print("The off-card SRK capture artifact was SHA-256 verified after publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
