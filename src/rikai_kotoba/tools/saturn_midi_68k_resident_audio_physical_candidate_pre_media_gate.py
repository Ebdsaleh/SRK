"""CLI for independent read-only R23 MIDI->SCSP pre-media review."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate import (
    build_srk_saturn_midi_68k_r23_physical_snapshot,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_audio_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-audio-physical-candidate-pre-media-gate",
        description=(
            "Independently verify the completed R23 32+2 MIDI->SCSP candidate "
            "and produce a read-only SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_midi_68k_resident_audio_physical_candidate_pre_media(
            args.project,
            args.card_root,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_voice_header_sha256=args.expected_voice_header_sha256,
            expected_producer_source_sha256=args.expected_producer_source_sha256,
            expected_producer_header_sha256=args.expected_producer_header_sha256,
            expected_resident_object_sha256=args.expected_resident_object_sha256,
            expected_producer_object_sha256=args.expected_producer_object_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()
    print("SRK R23 resident MIDI 68K -> SCSP pre-media gate")
    print("--------------------------------------------------")
    print(f"Project                    : {result.project_root}")
    print(f"Manifest SHA-256           : {result.manifest_sha256}")
    print(f"Build report SHA-256       : {result.report_sha256}")
    print(f"Audio image SHA-256        : {result.image_sha256}")
    print(f"Candidate main SHA-256     : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256     : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256      : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256       : {result.proof_header_sha256}")
    print(f"Proof source SHA-256       : {result.proof_source_sha256}")
    print(f"Proof records              : {result.proof_records}")
    print(f"Batch split                : {result.batch1_records}+{result.batch2_records}")
    print(
        "Scheduler clocks           : "
        f"{result.clock_zero_us} / {result.clock_partial_us} / {result.clock_batch1_us} us"
    )
    print(f"MIDI Note On clock         : {result.note_on_clock_us} us")
    print(f"MIDI Note Off clock        : {result.note_off_clock_us} us")
    print(f"Audible hold polls         : {result.audible_hold_polls}")
    print(f"Summary words verified     : {result.summary_words_verified}")
    print(f"Controller words verified  : {result.controller_words_verified}")
    print(f"Active-note words verified : {result.active_note_words_verified}")
    print(f"Voice-state words verified : {result.voice_words_verified}")
    print("R22A refill/timing contract: RE-PROVEN")
    print("SCSP slot-0 key-on readback: REQUIRED")
    print("Scheduled Note Off         : REQUIRED")
    print("SCSP slot-0 key-off readback: REQUIRED")
    print("Audible MIDI-driven note   : REQUIRED PHYSICALLY")
    print()
    print("Expected final software state")
    print(f"  CC74                     : {snapshot.cc74}")
    print(f"  Active notes             : {snapshot.final_active_note_count}")
    print(f"  Total records / batches  : {snapshot.total_records} / {snapshot.batches}")
    print(f"  Voice key on / off       : {snapshot.voice_key_on_count} / {snapshot.voice_key_off_count}")
    print()
    print("Read-only SAROO plan")
    print(f"Card root                  : {plan.card_root}")
    if plan.category_directory is not None:
        print(f"Category                   : {plan.category_directory.name}")
    else:
        print("Category                   : none")
    print(f"Destination                : {plan.destination_directory}")
    print(f"Source BIN                 : {plan.source_bin}")
    print(f"BIN size                   : {plan.bin_size} bytes")
    print(f"BIN SHA-256                : {result.deployable_bin_sha256}")
    print(f"Source CUE                 : {plan.source_cue}")
    print(f"CUE size                   : {plan.cue_size} bytes")
    print(f"CUE SHA-256                : {result.deployable_cue_sha256}")
    print(f"MODE1 sectors              : {plan.sector_count}")
    print(f"Raw track bytes            : {plan.raw_bytes}")
    print("Fresh MODE1 verification   : PASS")
    print("Candidate provenance       : PASS")
    print("Compiler provenance        : PASS")
    print("32+2 scheduler/audio proof : PASS")
    print("Full MIDI-state proof      : PASS")
    print("Voice-state proof          : PASS")
    print("Externally accepted hashes : PASS")
    print("SAROO destination          : FRESH")
    print("SAROO writes               : NONE")
    print()
    print("Result                     : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
