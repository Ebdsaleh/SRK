"""CLI for SRK's off-card silent full-batch Saturn MIDI 68K compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_compile_probe import (
    SaturnMidi68KSilentBatchCompileProbeError,
    probe_saturn_midi_68k_silent_batch_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-silent-batch-compile-probe",
        description=(
            "Generate and compile SRK's silent full-batch MC68EC000 constant program "
            "representation with the discovered SH-ELF GCC backend. No link, ISO, "
            "SAROO, Sound RAM installation, SCSP, SMPC, reset-vector, or 68K execution "
            "action occurs."
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
        help="Fresh off-card directory for generated source/object/log/report evidence",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_silent_batch_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KSilentBatchCompileProbeError) as exc:
        print(
            "srk-saturn-midi-68k-silent-batch-compile-probe: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK silent full-batch Saturn MIDI 68K compiler probe")
    print("----------------------------------------------------")
    print(f"Output           : {result.output_root}")
    print(f"Compiler         : {result.compiler}")
    print(f"Image SHA-256    : {result.image_sha256}")
    print(f"Source           : {result.source_path}")
    print(f"Source SHA-256   : {result.source_sha256}")
    print(f"Header           : {result.header_path}")
    print(f"Header SHA-256   : {result.header_sha256}")
    if result.object_path is not None:
        print(f"Object           : {result.object_path}")
        print(f"Object SHA-256   : {result.object_sha256}")
    else:
        print("Object           : not produced")
    print(f"Log              : {result.log_path}")
    print(f"Report           : {result.report_path}")
    print()
    if result.successful:
        print("Result           : SUCCESS")
        print("Legacy SH-ELF GCC accepted the generated silent full-batch MIDI 68K program representation.")
    else:
        print("Result           : FAILED")
        print(
            "No linker, ISO builder, SAROO card, Sound RAM install, SCSP, SMPC, "
            "reset-vector, or MC68EC000 execution action was attempted."
        )
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
