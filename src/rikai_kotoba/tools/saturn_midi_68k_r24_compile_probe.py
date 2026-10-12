"""CLI for the R24 complete real-MIDI compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r24_compile_probe import (
    SaturnMidi68KR24CompileProbeError,
    probe_saturn_midi_68k_r24_compile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    build_saturn_midi_68k_r24_song_profile,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r24-compile-probe",
        description=(
            "Compile SRK's R24 two-slot MC68EC000 audio image, complete real-SMF "
            "10-batch producer and SH-2 FRT backend without executing hardware I/O."
        ),
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_r24_compile(
            args.saturn_root,
            args.midi,
            args.output,
        )
        profile = build_saturn_midi_68k_r24_song_profile(args.midi)
        image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    except (OSError, SaturnMidi68KR24CompileProbeError, RuntimeError) as exc:
        print(
            f"srk-saturn-midi-68k-r24-compile-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK R24 real-SMF MIDI -> MC68EC000 -> SCSP compiler gate")
    print("---------------------------------------------------------")
    print(f"Compiler                  : {result.compiler}")
    print(f"Source MIDI               : {result.source_midi_path}")
    print(f"Source MIDI SHA-256       : {result.source_midi_sha256}")
    print(f"SRKM records              : {profile.record_count}")
    print(f"Duration                  : {profile.duration_us} us")
    print(f"Queue batches             : {len(profile.batches)}")
    print("Batch sizes               : " + "+".join(str(batch.record_count) for batch in profile.batches))
    print(f"Peak polyphony            : {profile.peak_polyphony}")
    print(f"Note range                : {profile.note_min}..{profile.note_max}")
    print(f"Resident image SHA-256    : {result.image_sha256}")
    print(f"Resident words            : {image.word_count}")
    print(f"Resident bytes            : {image.byte_size}")
    print(f"Resident range            : 0x00004000-0x{image.end_address:08X}")
    print("Voice allocator           : SCSP slots 0+1 / lowest free / no steal")
    print("Pitch                     : calibrated R24 MIDI table")
    print("Velocity                  : 128-entry mixer table")
    print("Clock backend             : SH-2 FRT / caller-selected source_hz")
    print("Physical frequency chosen : NO")
    print("SCSP execution            : NO")
    print("FRT execution             : NO")
    print("MC68EC000 execution       : NO")
    print("SAROO writes              : NONE")
    for name, value in result.generated_sha256:
        print(f"Generated {name} SHA-256 : {value}")
    for name, value in result.object_sha256:
        print(f"Object {name} SHA-256    : {value}")
    print(f"Report                    : {result.report_path}")
    print(f"Result                    : {'SUCCESS' if result.successful else 'FAIL'}")
    if result.successful:
        print("Legacy SH-ELF GCC accepted the complete inert R24 representations.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
