"""Inspect SRK's persistent SAROO resident-runtime proof artifact read-only."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_proof import (
    SarooRuntimeResidentProofError,
    inspect_runtime_resident_proof,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-resident-proof-inspect",
        description=(
            "Read SRK_RUNTIME_PROOF.BIN from a mounted SAROO card and report the "
            "armed / installed / proven stages without modifying the card."
        ),
    )
    parser.add_argument("card_root", help="root directory of the mounted SAROO SD card")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = inspect_runtime_resident_proof(args.card_root)
    except SarooRuntimeResidentProofError as exc:
        print(f"srk-saroo-runtime-resident-proof-inspect: {exc}")
        return 2

    print("SRK SAROO persistent resident-runtime proof")
    print("------------------------------------------------")
    print(f"Card root    : {report.card_root}")
    print(f"Proof file   : {report.proof_path}")
    print("Access policy: read-only inspection")
    print()

    for slot in report.slots:
        print(f"Slot {slot.index}: {slot.stage_name.upper()}")
        print(f"  Callback count : {slot.count}")
        print(f"  SS_TIMER ticks : {slot.timer_ticks}")
        print(f"  Since arm      : {slot.elapsed_ticks} us")
        print(f"  Vector         : 0x{slot.vector_address:08X}")
        print(f"  Return         : 0x{slot.return_address:08X}")
        print(f"  Proof threshold: {slot.threshold}")

    print()
    print("Result        : " + ("PROVEN" if report.proven else "NOT YET PROVEN"))
    print("Timer basis   : SAROO FPGA SS_TIMER (1 MHz hardware counter)")
    print("The mounted SAROO SD card was read only and was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
