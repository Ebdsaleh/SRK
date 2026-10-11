"""CLI for the Phase-B resident MIDI state-decoder compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder import (
    build_srk_saturn_midi_68k_resident_state_decoder_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_compile_probe import (
    SaturnMidi68KResidentStateDecoderCompileProbeError,
    probe_saturn_midi_68k_resident_state_decoder_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-state-decoder-compile-probe",
        description=(
            "Compile SRK's generated Phase-B MC68EC000 resident state decoder "
            "as inert C constant data with the production SH-ELF compiler policy."
        ),
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_resident_state_decoder_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KResidentStateDecoderCompileProbeError) as exc:
        print(
            "srk-saturn-midi-68k-resident-state-decoder-compile-probe: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    print("SRK Phase-B resident MIDI 68K state decoder compiler gate")
    print("----------------------------------------------------------")
    print(f"Compiler          : {result.compiler}")
    print(f"Image SHA-256     : {result.image_sha256}")
    print(f"Words             : {image.word_count}")
    print(f"Bytes             : {image.byte_size}")
    print(f"Program range     : 0x00004000-0x{image.end_address:08X}")
    print("Runtime records   : 1..32")
    print("State mutation    : ALL 7 SRKM v1 opcodes")
    print("Channel summaries : YES")
    print("Controller matrix : YES")
    print("Active-note bitmap: YES")
    print("MIDI-driven SCSP  : NO")
    print(f"Source SHA-256    : {result.source_sha256}")
    print(f"Header SHA-256    : {result.header_sha256}")
    print(f"Object SHA-256    : {result.object_sha256 or 'MISSING'}")
    print(f"Report            : {result.report_path}")
    print(f"Result            : {'SUCCESS' if result.successful else 'FAIL'}")
    if result.successful:
        print("Legacy SH-ELF GCC accepted the generated Phase-B state decoder representation.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
