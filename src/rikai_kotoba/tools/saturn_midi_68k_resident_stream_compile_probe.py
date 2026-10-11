"""CLI for the continuous MIDI 68K stream-service compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_compile_probe import (
    SaturnMidi68KResidentStreamCompileProbeError,
    probe_saturn_midi_68k_resident_stream_compile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-stream-compile-probe",
        description=(
            "Compile SRK's continuous MC68EC000 stream/scheduler image and "
            "SH-2 refill/timebase producer with the production legacy compiler policy."
        ),
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_resident_stream_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KResidentStreamCompileProbeError) as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-compile-probe: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    print("SRK resident MIDI 68K multi-batch/timestamp service compiler gate")
    print("----------------------------------------------------------------")
    print(f"Compiler                    : {result.compiler}")
    print(f"Image SHA-256               : {result.image_sha256}")
    print(f"Words                       : {image.word_count}")
    print(f"Bytes                       : {image.byte_size}")
    print(f"Program range               : 0x00004000-0x{image.end_address:08X}")
    print("Queue refill                : 1..32 records per batch")
    print("Sequence service            : strict non-zero 16-bit, FFFF -> 1")
    print("State across refills        : PERSISTENT")
    print("Timestamp scheduler         : MC68EC000 gated")
    print("Clock publication           : 32-bit us + odd/even generation seqlock")
    print("MIDI-driven SCSP            : NO")
    print(f"Resident source SHA-256     : {result.resident_source_sha256}")
    print(f"Resident header SHA-256     : {result.resident_header_sha256}")
    print(f"Producer source SHA-256     : {result.producer_source_sha256}")
    print(f"Producer header SHA-256     : {result.producer_header_sha256}")
    print(f"Resident object SHA-256     : {result.resident_object_sha256 or 'MISSING'}")
    print(f"Producer object SHA-256     : {result.producer_object_sha256 or 'MISSING'}")
    print(f"Report                      : {result.report_path}")
    print(f"Result                      : {'SUCCESS' if result.successful else 'FAIL'}")
    if result.successful:
        print("Legacy SH-ELF GCC accepted both continuous-service representations.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
