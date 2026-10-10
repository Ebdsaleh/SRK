"""CLI for SRK's off-card bounded Saturn MIDI 68K installer compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_installer_compile_probe import (
    SaturnMidi68KInstallerCompileProbeError,
    probe_saturn_midi_68k_installer_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-installer-compile-probe",
        description=(
            "Compile SRK's bounded Saturn MIDI MC68EC000 installer with the "
            "discovered SH-ELF GCC backend. No link, ISO, SAROO, Sound RAM, "
            "reset-vector, SMPC, SCSP, or MC68EC000 runtime action occurs."
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
        result = probe_saturn_midi_68k_installer_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KInstallerCompileProbeError) as exc:
        print(
            f"srk-saturn-midi-68k-installer-compile-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK bounded Saturn MIDI 68K installer compiler probe")
    print("----------------------------------------------------")
    print(f"Output                    : {result.output_root}")
    print(f"Compiler                  : {result.compiler}")
    print(f"Source SHA-256            : {result.source_sha256}")
    print(f"Installer header SHA-256  : {result.installer_header_sha256}")
    print(f"Program header SHA-256    : {result.program_header_sha256}")
    if result.object_path is not None:
        print(f"Object                    : {result.object_path}")
        print(f"Object SHA-256            : {result.object_sha256}")
    else:
        print("Object                    : not produced")
    print(f"Log                       : {result.log_path}")
    print(f"Report                    : {result.report_path}")
    print()
    if result.successful:
        print("Result                    : SUCCESS")
        print("Legacy SH-ELF GCC accepted the bounded MIDI 68K installer.")
    else:
        print("Result                    : FAILED")
        print(
            "No linker, ISO builder, SAROO card, Sound RAM write, reset-vector "
            "change, SMPC command, SCSP access, or MC68EC000 action was attempted."
        )
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
