"""Prepare a separate SAROO tree for one-shot game-entry WRAM-H capture."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.ingame_entry_integration import (
    prepare_ingame_entry_capture_tree,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-ingame-entry-prepare",
        description=(
            "Copy an existing SRK capture-menu SAROO tree to a new directory and "
            "add one-shot title-neutral game-entry WRAM-H capture support."
        ),
    )
    parser.add_argument(
        "source",
        help="Existing SRK capture-menu tree (for example SAROO-SRK-CAPTURE)",
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
        result = prepare_ingame_entry_capture_tree(args.source, args.output)
    except Exception as exc:
        print(f"srk-saroo-ingame-entry-prepare: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK SAROO in-game entry-capture tree prepared")
    print("-" * 52)
    print(f"Source tree      : {result.source_root}")
    print(f"Output tree      : {result.output_root}")
    print(f"Patched main.c   : {result.main_path}")
    print(f"Patched game_load: {result.game_load_path}")
    print(f"Patched helper   : {result.helper_source_path}")
    print(f"Marker           : {result.marker_path}")
    print()
    print("Source capture-menu tree was not modified.")
    print("New menu action  : SRK Arm Game-Entry Capture")
    print("Trigger          : BIOS game-entry pointer at load time (title-neutral)")
    print("Output           : /SAROO/SRK_GAME_WRAMH.BIN (1 MiB WRAM-H)")
    print("Behavior         : one-shot; UBR disarmed before SD I/O; game resumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
