"""CLI for the Sega Sound I/F Direct MIDI compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.sbl_direct_midi_compile_probe import (
    SaturnSblDirectMidiCompileProbeError,
    probe_saturn_sbl_direct_midi_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-direct-midi-compile-probe",
        description=(
            "Compile SRK's exact SND_CtrlDirMidi adapter against the installed "
            "Sega Sound Driver header using the legacy SH-ELF GCC backend."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root containing the installed Sega SDK and SH-ELF compiler",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card evidence directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_sbl_direct_midi_compile(args.saturn_root, args.output)
    except (OSError, SaturnSblDirectMidiCompileProbeError) as exc:
        print(
            f"srk-saturn-sbl-direct-midi-compile-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Sega Sound I/F Direct MIDI compiler gate")
    print("--------------------------------------------")
    print(f"Output                    : {result.output_root}")
    print(f"Compiler                  : {result.compiler}")
    print(f"Sega header               : {result.sega_header}")
    print(f"Sega sound library        : {result.sega_library}")
    print(f"Source SHA-256            : {result.source_sha256}")
    print(f"Adapter header SHA-256    : {result.adapter_header_sha256}")
    print(f"Sega header SHA-256       : {result.sega_header_sha256}")
    print(f"Sega library SHA-256      : {result.sega_library_sha256}")
    print(f"Object                    : {result.object_path or '[none]'}")
    print(f"Object SHA-256            : {result.object_sha256 or '[none]'}")
    print(f"Log                       : {result.log_path}")
    print(f"Report                    : {result.report_path}")
    print()

    if result.successful:
        print("Result                    : SUCCESS")
        print("Legacy SH-ELF GCC accepted the exact Sega SND_CtrlDirMidi adapter.")
        print("No link, Saturn execution, ISO build, or SAROO write was performed.")
        return 0

    print("Result                    : FAILED")
    print("Preserve the evidence directory and stop before integration/build work.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
