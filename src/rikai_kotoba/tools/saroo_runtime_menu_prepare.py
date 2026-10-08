"""Prepare a separate SAROO tree with SRK runtime-menu input observation."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_menu_integration import (
    prepare_runtime_menu_input_tree,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-menu-prepare",
        description=(
            "Copy a validated SRK SAROO capture-menu tree and add the title-neutral "
            "L+R runtime-menu input hook. This preparation layer performs no SD writes."
        ),
    )
    parser.add_argument(
        "source_tree",
        help="Existing SRK capture-menu generated tree",
    )
    parser.add_argument(
        "output_tree",
        help="New output directory; it must not already exist",
    )
    parser.add_argument(
        "--helper-root",
        default=None,
        help="Optional directory containing srk_runtime_input.c/.h",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = prepare_runtime_menu_input_tree(
            args.source_tree,
            args.output_tree,
            helper_root=args.helper_root,
        )
    except Exception as exc:
        print(
            f"srk-saroo-runtime-menu-prepare: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK SAROO runtime-menu input-hook tree prepared")
    print("-" * 52)
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Runtime helper    : {result.runtime_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source capture-menu tree was not modified.")
    print("Input source      : completed BIOS controller sample (controller 1)")
    print("Activation        : hold Saturn L+R for 50 consecutive completed samples")
    print("Current action    : internal runtime-menu request latch only")
    print("Safety            : no SD writes, RAM captures, SMPC polling, or VDP changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
