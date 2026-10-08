"""Prepare a separate SAROO tree with SRK's modal red runtime shell."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_modal_red_integration import (
    SarooRuntimeModalRedIntegrationError,
    prepare_runtime_modal_red_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-modal-red-prepare",
        description=(
            "Create a separate SRK/SAROO tree that enters a solid-red modal "
            "runtime state on L+R and restores the exact captured VDP2 "
            "color-offset state on a second release-gated L+R hold."
        ),
    )
    parser.add_argument("source", help="validated SRK runtime-video canary tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_modal_red_tree(args.source, args.output)
    except SarooRuntimeModalRedIntegrationError as exc:
        print(f"srk-saroo-runtime-modal-red-prepare: {exc}")
        return 2

    print("SRK SAROO modal red-shell tree prepared")
    print("----------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Modal helper      : {result.modal_source_path}")
    print(f"Canary helper     : {result.canary_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source runtime-canary tree was not modified.")
    print("Open               : hardware-validated L+R hold event")
    print("Display            : solid-red VDP2 color-offset modal surface")
    print("Title main path    : blocked inside the existing BIOS controller hook")
    print("Modal input        : original BIOS controller routine once per display frame")
    print("Dismiss            : release L+R, then hold L+R for 50 fresh samples")
    print("Fail-safe          : automatic restore after 600 display frames")
    print("Restore            : exact captured VDP2 color-offset register values")
    print("Safety             : no VRAM/CRAM/VDP1 writes, SD writes, RAM captures, or direct SMPC polling")
    print("Scope              : modal lifecycle proof only; not the final text menu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
