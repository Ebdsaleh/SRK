"""Prepare a separate SAROO tree with SRK's read-only runtime VDP2 snapshot."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_video_state_integration import (
    SarooRuntimeVideoStateIntegrationError,
    prepare_runtime_video_state_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-video-state-prepare",
        description=(
            "Create a separate SRK/SAROO tree that snapshots only the VDP2 "
            "color-offset register set when the runtime menu opens."
        ),
    )
    parser.add_argument("source", help="validated SRK runtime-menu state tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_video_state_tree(args.source, args.output)
    except SarooRuntimeVideoStateIntegrationError as exc:
        print(f"srk-saroo-runtime-video-state-prepare: {exc}")
        return 2

    print("SRK SAROO runtime-video state tree prepared")
    print("----------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Video helper      : {result.video_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source runtime-state tree was not modified.")
    print("Menu-open action   : read-only VDP2 color-offset register snapshot")
    print("Resume action      : discard in-memory snapshot")
    print("Current renderer   : none")
    print("Safety             : no VDP/VRAM/CRAM writes, SD writes, RAM captures, or direct SMPC polling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
