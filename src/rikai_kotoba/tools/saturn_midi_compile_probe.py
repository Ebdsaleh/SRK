"""CLI for SRK's off-card inert Saturn MIDI bridge compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_compile_probe import (
    SaturnMidiCompileProbeError,
    probe_saturn_midi_bridge_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-compile-probe",
        description=(
            "Compile SRK's inert generated Saturn MIDI bridge with the discovered "
            "SH-ELF GCC backend. No link, ISO, SAROO, Sound RAM, or SCSP write occurs."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root containing the SH-ELF toolchain",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card directory for object/log/report evidence",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_bridge_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidiCompileProbeError) as exc:
        print(f"srk-saturn-midi-compile-probe: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK inert Saturn MIDI bridge compiler probe")
    print("--------------------------------------------")
    print(f"Output          : {result.output_root}")
    print(f"Compiler        : {result.compiler}")
    print(f"Source SHA-256  : {result.source_sha256}")
    print(f"Header SHA-256  : {result.header_sha256}")
    if result.object_path is not None:
        print(f"Object          : {result.object_path}")
        print(f"Object SHA-256  : {result.object_sha256}")
    else:
        print("Object          : not produced")
    print(f"Log             : {result.log_path}")
    print(f"Report          : {result.report_path}")
    print()
    if result.successful:
        print("Result          : SUCCESS")
        print("Legacy SH-ELF GCC accepted the inert generated MIDI bridge.")
    else:
        print("Result          : FAILED")
        print("No linker, ISO builder, SAROO card, Sound RAM, or SCSP write was attempted.")
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
