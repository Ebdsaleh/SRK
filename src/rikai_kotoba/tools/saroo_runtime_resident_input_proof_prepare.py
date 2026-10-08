"""Prepare a separate SAROO tree for SRK's R9 resident runtime-input proof."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_input_proof_integration import (
    SarooRuntimeResidentInputProofIntegrationError,
    prepare_runtime_resident_input_proof_tree,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-resident-input-proof-prepare",
        description=(
            "Create a separate SRK/SAROO tree that keeps the context-safe "
            "HBLANK-IN resident trampoline active until a rate-limited L+R "
            "hold is observed, then persists one activation proof."
        ),
    )
    parser.add_argument("source", help="validated SRK capture-menu tree")
    parser.add_argument("output", help="new output directory; must not already exist")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_runtime_resident_input_proof_tree(args.source, args.output)
    except SarooRuntimeResidentInputProofIntegrationError as exc:
        print(f"srk-saroo-runtime-resident-input-proof-prepare: {exc}")
        return 2

    print("SRK SAROO R9 resident runtime-input proof tree prepared")
    print("------------------------------------------------------")
    print(f"Source tree       : {result.source_root}")
    print(f"Output tree       : {result.output_root}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched main.c    : {result.main_path}")
    print(f"Patched game_load : {result.game_load_path}")
    print(f"Input helper      : {result.runtime_input_source_path}")
    print(f"Proof helper      : {result.proof_source_path}")
    print(f"Trampoline        : {result.trampoline_source_path}")
    print(f"Marker            : {result.marker_path}")
    print()
    print("Source capture-menu tree was not modified.")
    print("Arm                : SRK Arm Runtime Input in SAROO menu")
    print("Runtime hook       : context-safe BIOS HBLANK-IN trampoline at 0x0600090C")
    print("Input source       : BIOS controller-1 snapshot at 0x06020232")
    print("Sampling           : 20000 SS_TIMER ticks (20 ms) minimum interval")
    print("Activation         : L+R for 50 rate-limited samples (~1 second)")
    print("Persistent output  : /SAROO/SRK_RUNTIME_INPUT_PROOF.BIN (96 bytes)")
    print("Direct SMPC polling: none")
    print("VDP dependency     : none")
    print("Waiting SD I/O     : none")
    print("Activation SD I/O  : one preallocated 32-byte proof-slot update")
    print("Restore            : original BIOS HBLANK-IN vector restored after activation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
