"""CLI for the Sega Sound I/F Direct MIDI link gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.sbl_direct_midi_link_probe import (
    SaturnSblDirectMidiLinkProbeError,
    probe_saturn_sbl_direct_midi_link,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-direct-midi-link-probe",
        description=(
            "Compile SRK's exact Sega Direct MIDI adapter, bind it against the "
            "installed sega_snd.a, and inspect the remaining transitive symbols "
            "without building an executable or touching Saturn/SAROO."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root containing the accepted Sega Sound SDK",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card evidence directory for the link gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_sbl_direct_midi_link(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnSblDirectMidiLinkProbeError) as exc:
        print(
            f"srk-saturn-sbl-direct-midi-link-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            f"srk-saturn-sbl-direct-midi-link-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Sega Sound I/F Direct MIDI link gate")
    print("----------------------------------------")
    print(f"Output                    : {result.output_root}")
    print(f"Compiler                  : {result.compiler}")
    print(f"Objdump                   : {result.objdump}")
    print(f"Sega header               : {result.sega_header}")
    print(f"Sega sound library        : {result.sega_library}")
    print(f"Compiled object           : {result.object_path or '[none]'}")
    print(f"Linked object             : {result.linked_object_path or '[none]'}")
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
        print("sega_snd.a satisfied SND_CtrlDirMidi with no remaining undefined symbols.")
        print("No executable, ISO, Saturn execution, or SAROO write was performed.")
        return 0

    if result.direct_midi_resolved:
        print("Result                    : DEPENDENCY CLOSURE REQUIRED")
        print(
            "sega_snd.a owns the Direct MIDI call; use the exact undefined symbols "
            "above to close only the required transitive libraries."
        )
    else:
        print("Result                    : FAILED")
        print("The exact sega_snd.a did not satisfy SND_CtrlDirMidi in this link.")
    print("No executable, ISO, Saturn execution, or SAROO write was performed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
