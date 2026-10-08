"""Prepare a separate SAROO tree for SRK's armed post-entry execution proof."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_execution_proof_integration import (
    SarooRuntimeExecutionProofIntegrationError,
    prepare_runtime_execution_proof_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-execution-proof-prepare",
        description=(
            "Create a separate R6 SRK/SAROO tree that is armed in the SAROO menu, "
            "gates on the title's IP.BIN 1st-read breakpoint, and proves later "
            "cdp_hook execution with an input-independent temporary display blank."
        ),
    )
    parser.add_argument("source", help="validated R4 runtime-video canary tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_execution_proof_tree(args.source, args.output)
    except SarooRuntimeExecutionProofIntegrationError as exc:
        print(f"srk-saroo-runtime-execution-proof-prepare: {exc}")
        return 2

    print("SRK SAROO runtime execution-proof tree prepared")
    print("-------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched main.c    : {result.main_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Proof helper      : {result.helper_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source R4 tree was not modified.")
    print("Arm                : SRK Arm Runtime Proof in SAROO menu")
    print("Entry gate         : dynamic IP.BIN 1st-read UBR breakpoint")
    print("Proof threshold    : 600 later cdp_hook callbacks")
    print("Visible proof      : display blank for 120 frames, then exact TVMD restore")
    print("Input dependency   : none")
    print("Safety             : no SD writes, RAM captures, direct SMPC polling, VRAM/CRAM writes, or VDP1 writes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
