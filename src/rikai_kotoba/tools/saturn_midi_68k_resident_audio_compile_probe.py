"""CLI for the R23 resident MIDI/SCSP compiler gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_service import (
    build_srk_saturn_midi_68k_resident_audio_service_image,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_compile_probe import (
    SaturnMidi68KResidentAudioCompileProbeError,
    probe_saturn_midi_68k_resident_audio_compile,
)
from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_HOLD_US,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_SLOT,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-audio-compile-probe",
        description=(
            "Compile SRK's R23 MC68EC000 stream + monophonic SCSP service and "
            "existing SH-2 refill/timebase producer without installing or executing it."
        ),
    )
    parser.add_argument("--saturn-root", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = probe_saturn_midi_68k_resident_audio_compile(
            args.saturn_root,
            args.output,
        )
    except (OSError, SaturnMidi68KResidentAudioCompileProbeError) as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-compile-probe: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    print("SRK R23 resident MIDI 68K -> SCSP first-audio compiler gate")
    print("-----------------------------------------------------------")
    print(f"Compiler                    : {result.compiler}")
    print(f"Image SHA-256               : {result.image_sha256}")
    print(f"Words                       : {image.word_count}")
    print(f"Bytes                       : {image.byte_size}")
    print(f"Program range               : 0x00004000-0x{image.end_address:08X}")
    print("Queue/refill semantics      : R22A-compatible")
    print("Timestamp scheduler         : MC68EC000 gated")
    print("Voice allocator             : slot 0 / monophonic / no steal")
    print(f"Voice state                 : 0x{SATURN_MIDI_68K_VOICE_STATE_ADDRESS:08X}")
    print(f"PCM waveform                : 0x{SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS:08X}")
    print(f"68K SCSP register base      : 0x{SATURN_MIDI_68K_SCSP_REGISTER_BASE:08X}")
    print(f"First-note proof            : ch{SATURN_MIDI_68K_R23_CHANNEL} note {SATURN_MIDI_68K_R23_NOTE} vel {SATURN_MIDI_68K_R23_VELOCITY}")
    print(f"Owned SCSP slot             : {SATURN_MIDI_68K_R23_SLOT}")
    print(f"Scheduled hold              : {SATURN_MIDI_68K_R23_HOLD_US} us")
    print("MIDI-driven SCSP image      : YES")
    print("Build-time SCSP execution   : NO")
    print("SAROO writes                : NONE")
    print(f"Resident source SHA-256     : {result.resident_source_sha256}")
    print(f"Resident header SHA-256     : {result.resident_header_sha256}")
    print(f"Producer source SHA-256     : {result.producer_source_sha256}")
    print(f"Producer header SHA-256     : {result.producer_header_sha256}")
    print(f"Voice header SHA-256        : {result.voice_header_sha256}")
    print(f"Resident object SHA-256     : {result.resident_object_sha256 or 'MISSING'}")
    print(f"Producer object SHA-256     : {result.producer_object_sha256 or 'MISSING'}")
    print(f"Report                      : {result.report_path}")
    print(f"Result                      : {'SUCCESS' if result.successful else 'FAIL'}")
    if result.successful:
        print("Legacy SH-ELF GCC accepted the inert R23 audio representations.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
