"""Prepare a separate SAROO tree with SRK's bounded visible video canary."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_video_canary_integration import (
    SarooRuntimeVideoCanaryIntegrationError,
    prepare_runtime_video_canary_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-video-canary-prepare",
        description=(
            "Create a separate SRK/SAROO tree that flashes a bounded red VDP2 "
            "color-offset canary and restores the exact captured register state."
        ),
    )
    parser.add_argument("source", help="validated SRK runtime-video state tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_video_canary_tree(args.source, args.output)
    except SarooRuntimeVideoCanaryIntegrationError as exc:
        print(f"srk-saroo-runtime-video-canary-prepare: {exc}")
        return 2

    print("SRK SAROO bounded runtime-video canary tree prepared")
    print("------------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Canary helper     : {result.canary_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source runtime-video tree was not modified.")
    print("Activation         : hardware-validated L+R hold event")
    print("Visible action     : red VDP2 color-offset pulse for three display frames")
    print("Restore            : exact captured color-offset registers before return")
    print("Safety             : no VRAM/CRAM/VDP1 writes, SD writes, RAM captures, or direct SMPC polling")
    print("Scope              : visibility/restore canary only; not the final text menu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
