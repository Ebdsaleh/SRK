"""CLI for the Sega Direct MIDI dependency-closure gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.sbl_direct_midi_closure_gate import (
    SaturnSblDirectMidiClosureGateError,
    probe_saturn_sbl_direct_midi_closure,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-direct-midi-closure-gate",
        description=(
            "Close the exact sega_snd.a Direct MIDI dependencies using SRK's "
            "freestanding memcpy/memset and the libgcc selected by the installed "
            "SH-ELF compiler."
        ),
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_sbl_direct_midi_closure(args.saturn_root, args.output)
    except (OSError, SaturnSblDirectMidiClosureGateError) as exc:
        print(
            f"srk-saturn-sbl-direct-midi-closure-gate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Sega Direct MIDI dependency closure gate")
    print("--------------------------------------------")
    print(f"Output                    : {result.output_root}")
    print(f"Compiler                  : {result.compiler}")
    print(f"Objdump                   : {result.objdump}")
    print(f"Sega sound library        : {result.sega_library}")
    print(f"Exact libgcc              : {result.libgcc}")
    print(f"Linked object             : {result.linked_object or '[none]'}")
    print(
        "SND_CtrlDirMidi binding  : "
        + ("RESOLVED" if result.direct_midi_resolved else "UNRESOLVED")
    )
    print(f"Undefined symbols         : {len(result.undefined_symbols)}")
    for symbol in result.undefined_symbols:
        print(f"  {symbol}")
    print(
        "Transitive closure       : "
        + ("COMPLETE" if result.closure_complete else "INCOMPLETE")
    )
    print(f"Log                       : {result.log_path}")
    print(f"Report                    : {result.report_path}")
    print()

    if result.successful:
        print("Result                    : SUCCESS")
        print("The Sega Direct MIDI call now has a complete relocatable link closure.")
        print("No executable, ISO, Saturn execution, or SAROO write was performed.")
        return 0

    print("Result                    : INCOMPLETE")
    print("Use only the exact undefined symbols above for the next closure step.")
    print("No executable, ISO, Saturn execution, or SAROO write was performed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
