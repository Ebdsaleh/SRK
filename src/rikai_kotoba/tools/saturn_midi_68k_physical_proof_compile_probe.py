"""CLI for SRK's silent Saturn MIDI 68K physical-proof compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof_compile_probe import (
    SaturnMidi68KPhysicalProofCompileProbeError,
    probe_saturn_midi_68k_physical_proof_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-physical-proof-compile-probe",
        description=(
            "Compile SRK's still-uninvoked silent MIDI MC68EC000 physical-proof "
            "controller with the legacy SH-ELF GCC backend without linking or "
            "touching Saturn hardware."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root used only to resolve the existing SH-ELF compiler",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card evidence directory for the compiler probe",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_physical_proof_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KPhysicalProofCompileProbeError) as exc:
        print(
            f"srk-saturn-midi-68k-physical-proof-compile-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            f"srk-saturn-midi-68k-physical-proof-compile-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK silent Saturn MIDI 68K physical-proof compiler probe")
    print("--------------------------------------------------------")
    print(f"Output                    : {result.output_root}")
    print(f"Compiler                  : {result.compiler}")
    print(f"Source SHA-256            : {result.source_sha256}")
    print(f"Proof header SHA-256      : {result.proof_header_sha256}")
    print(f"Runtime header SHA-256    : {result.runtime_header_sha256}")
    print(f"Adapter header SHA-256    : {result.adapter_header_sha256}")
    print(f"Object                    : {result.object_path or '[none]'}")
    print(f"Object SHA-256            : {result.object_sha256 or '[none]'}")
    print(f"Log                       : {result.log_path}")
    print(f"Report                    : {result.report_path}")
    print()

    if result.successful:
        print("Result                    : SUCCESS")
        print("Legacy SH-ELF GCC accepted the silent MIDI 68K physical-proof controller.")
        return 0

    print("Result                    : FAILED")
    print("Preserve this evidence directory and stop; do not proceed to a full build.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
