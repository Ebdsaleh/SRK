"""CLI for SRK's off-card general resident Saturn MIDI 68K compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder import (
    build_srk_saturn_midi_68k_resident_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_compile_probe import (
    SaturnMidi68KResidentDecoderCompileProbeError,
    probe_saturn_midi_68k_resident_decoder_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-decoder-compile-probe",
        description=(
            "Generate and compile SRK's general silent MC68EC000 resident decoder "
            "constant representation with the discovered SH-ELF GCC backend. No "
            "link, ISO, SAROO, Sound RAM installation, SCSP, SMPC, reset-vector, "
            "or 68K execution action occurs."
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
        result = probe_saturn_midi_68k_resident_decoder_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KResidentDecoderCompileProbeError) as exc:
        print(
            "srk-saturn-midi-68k-resident-decoder-compile-probe: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    print("SRK general silent Saturn MIDI 68K resident decoder compiler probe")
    print("----------------------------------------------------------------")
    print(f"Output           : {result.output_root}")
    print(f"Compiler         : {result.compiler}")
    print(f"Image SHA-256    : {result.image_sha256}")
    print(f"Words            : {image.word_count}")
    print(f"Bytes            : {image.byte_size}")
    print(f"Program range    : 0x00004000-0x{image.end_address:08X}")
    print("Runtime records  : 1..32")
    print("Embedded records : NONE")
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
        print(
            "Legacy SH-ELF GCC accepted the generated general silent MIDI 68K "
            "resident decoder representation."
        )
    else:
        print("Result           : FAILED")
        print(
            "No linker, ISO builder, SAROO card, Sound RAM install, SCSP, SMPC, "
            "reset-vector, or MC68EC000 execution action was attempted."
        )
    return 0 if result.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
