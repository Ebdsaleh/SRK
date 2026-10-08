"""Inspect SRK's R9 persistent resident runtime-input proof read-only."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from rikai_kotoba.hardware.saturn.saroo.runtime_resident_input_proof import (
    SarooRuntimeResidentInputProofError,
    inspect_runtime_resident_input_proof,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-runtime-resident-input-proof-inspect",
        description=(
            "Read SRK_RUNTIME_INPUT_PROOF.BIN from a mounted SAROO card and "
            "report armed / installed / activated stages without modifying it."
        ),
    )
    parser.add_argument("card_root", help="root directory of the mounted SAROO SD card")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = inspect_runtime_resident_input_proof(args.card_root)
    except SarooRuntimeResidentInputProofError as exc:
        print(f"srk-saroo-runtime-resident-input-proof-inspect: {exc}")
        return 2

    print("SRK SAROO R9 resident runtime-input proof")
    print("-----------------------------------------")
    print(f"Card root    : {report.card_root}")
    print(f"Proof file   : {report.proof_path}")
    print("Access policy: read-only inspection")
    print()

    for slot in report.slots:
        print(f"Slot {slot.index}: {slot.stage_name.upper()}")
        print(f"  Buttons        : 0x{slot.buttons:04X}")
        print(f"  Callback count : {slot.callback_count}")
        print(f"  Input samples  : {slot.sample_count}")
        print(f"  SS_TIMER ticks : {slot.timer_ticks}")
        print(f"  Since arm      : {slot.elapsed_ticks} us")
        print(f"  Sample period  : {slot.sample_period_us} us")
        print(f"  Hold threshold : {slot.hold_samples} samples")

    print()
    print("Result        : " + ("ACTIVATED" if report.activated else "NOT YET ACTIVATED"))
    print("Input source  : BIOS controller-1 snapshot at 0x06020232")
    print("Timer basis   : SAROO FPGA SS_TIMER (1 MHz hardware counter)")
    print("The mounted SAROO SD card was read only and was not modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
