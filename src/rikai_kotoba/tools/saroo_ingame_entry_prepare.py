"""Prepare a separate SAROO tree for one-shot in-game WRAM-H capture."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.ingame_entry_integration import (
    prepare_ingame_entry_capture_tree,
)


def _parse_pc(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "capture PC must be an integer such as 0x06012000"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-ingame-entry-prepare",
        description=(
            "Copy an existing SRK capture-menu SAROO tree to a new directory and "
            "add one-shot title-neutral execution capture. By default the trigger "
            "is the IP.BIN 1st-read transfer address; --capture-pc selects an "
            "explicit caller-supplied SH-2 PC instead."
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
    parser.add_argument(
        "--capture-pc",
        type=_parse_pc,
        default=None,
        help=(
            "Optional even SH-2 PC in WRAM-H (0x06000000-0x060FFFFF). "
            "The address is local generator input and is not embedded in public SRK source."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = prepare_ingame_entry_capture_tree(
            args.source,
            args.output,
            capture_pc=args.capture_pc,
        )
    except Exception as exc:
        print(f"srk-saroo-ingame-entry-prepare: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK SAROO execution-capture tree prepared")
    print("-" * 48)
    print(f"Source tree      : {result.source_root}")
    print(f"Output tree      : {result.output_root}")
    print(f"Patched main.c   : {result.main_path}")
    print(f"Patched game_load: {result.game_load_path}")
    print(f"Patched helper   : {result.helper_source_path}")
    print(f"Marker           : {result.marker_path}")
    print()
    print("Source capture-menu tree was not modified.")
    if result.capture_pc is None:
        print("New menu action  : SRK Arm 1st-Read Capture")
        print("Breakpoint source: big-endian IP.BIN 1st-read address at 0x060020F0")
        print("Boot-spec note   : loaded there; execution is title-dependent")
    else:
        print("New menu action  : SRK Arm PC Capture")
        print(f"Breakpoint source: caller-supplied SH-2 PC 0x{result.capture_pc:08X}")
        print("Address policy   : even PC inside WRAM-H; caller data stays outside public SRK")
    print("Output           : /SAROO/SRK_GAME_WRAMH.BIN (1 MiB WRAM-H)")
    print("Behavior         : one-shot; UBR disarmed before SD I/O; title resumes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
