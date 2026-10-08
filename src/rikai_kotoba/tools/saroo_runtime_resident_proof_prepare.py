"""Prepare a separate SAROO tree for SRK's persistent resident-runtime proof."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_proof_integration import (
    SarooRuntimeResidentProofIntegrationError,
    prepare_runtime_resident_proof_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-resident-proof-prepare",
        description=(
            "Create a separate SRK/SAROO tree that arms from the SAROO menu, "
            "installs a verified BIOS interrupt trampoline after 1ST_READ is loaded, "
            "and persists proof after 600 runtime callbacks."
        ),
    )
    parser.add_argument("source", help="validated SRK capture-menu tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_resident_proof_tree(args.source, args.output)
    except SarooRuntimeResidentProofIntegrationError as exc:
        print(f"srk-saroo-runtime-resident-proof-prepare: {exc}")
        return 2

    print("SRK SAROO persistent resident-runtime proof tree prepared")
    print("-------------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched main.c    : {result.main_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Proof helper      : {result.helper_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source capture-menu tree was not modified.")
    print("Arm                : SRK Arm Resident Proof in SAROO menu")
    print("Runtime hook       : verified BIOS interrupt trampoline at 0x0600090C")
    print("Proof threshold    : 600 trampoline callbacks")
    print("Persistent output  : /SAROO/SRK_RUNTIME_PROOF.BIN (96 bytes)")
    print("Timing             : raw SAROO FPGA SS_TIMER hardware ticks")
    print("Input dependency   : none")
    print("VDP dependency     : none")
    print("Runtime SD I/O     : one preallocated 32-byte proof-slot update")
    print("Restore            : original BIOS vector restored after the proof attempt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
