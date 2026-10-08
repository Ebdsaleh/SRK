"""Prepare a renderer-independent SRK runtime-menu state tree."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_menu_state_integration import (
    SarooRuntimeMenuStateIntegrationError,
    prepare_runtime_menu_state_tree,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-menu-state-prepare",
        description=(
            "Copy a hardware-validated SRK runtime-hook SAROO tree and add the "
            "renderer-independent runtime-menu state machine."
        ),
    )
    parser.add_argument("source", type=Path, help="validated SRK runtime-hook tree")
    parser.add_argument("output", type=Path, help="fresh output tree")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = prepare_runtime_menu_state_tree(args.source, args.output)
    except SarooRuntimeMenuStateIntegrationError as exc:
        parser.error(str(exc))

    print("SRK SAROO runtime-menu state tree prepared")
    print("----------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"State helper      : {result.state_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source runtime-hook tree was not modified.")
    print("Menu lifecycle     : open on validated L+R event; arm after shoulder release")
    print("Resume input       : new A, B, or Start press")
    print("Current renderer   : none")
    print("Safety             : no SD writes, RAM captures, direct SMPC polling, or VDP changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
