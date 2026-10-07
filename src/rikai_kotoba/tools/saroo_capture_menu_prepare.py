"""Prepare a second SRK SAROO tree with controller-accessible capture actions."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.capture_menu_integration import (
    prepare_capture_menu_tree,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-capture-menu",
        description=(
            "Copy an existing SRK-generated SAROO tree to a new directory and add "
            "controller-accessible Work RAM capture menu actions without modifying "
            "the source generated tree."
        ),
    )
    parser.add_argument(
        "source",
        help="Existing SRK-generated SAROO tree (for example SAROO-SRK)",
    )
    parser.add_argument(
        "output",
        help="New output tree; must not already exist",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = prepare_capture_menu_tree(args.source, args.output)
    except Exception as exc:
        print(f"srk-saroo-capture-menu: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK SAROO capture-menu tree prepared")
    print("-" * 44)
    print(f"Source tree      : {result.source_root}")
    print(f"Output tree      : {result.output_root}")
    print(f"Patched main.c   : {result.main_path}")
    print(f"Marker           : {result.marker_path}")
    print()
    print("Source generated tree was not modified.")
    print("New menu actions:")
    print("  SRK Capture WRAM-L -> /SAROO/SRK_WRAML.BIN")
    print("  SRK Capture WRAM-H -> /SAROO/SRK_WRAMH.BIN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
