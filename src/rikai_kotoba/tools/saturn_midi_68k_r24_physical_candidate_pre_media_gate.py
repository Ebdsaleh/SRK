"""CLI for independent read-only R24 real-SMF pre-media review."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_pre_media_gate import (
    SaturnMidi68KR24PhysicalCandidatePreMediaGateError,
    inspect_saturn_midi_68k_r24_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r24-physical-candidate-pre-media-gate",
        description=(
            "Independently revalidate the completed R24 real-SMF physical candidate "
            "and produce a read-only fresh SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-player-source-sha256", required=True)
    parser.add_argument("--expected-player-header-sha256", required=True)
    parser.add_argument("--expected-frt-source-sha256", required=True)
    parser.add_argument("--expected-frt-header-sha256", required=True)
    parser.add_argument("--expected-stream-source-sha256", required=True)
    parser.add_argument("--expected-stream-header-sha256", required=True)
    parser.add_argument("--expected-candidate-main-sha256", required=True)
    parser.add_argument("--expected-candidate-menu-sha256", required=True)
    parser.add_argument("--expected-runtime-sha256", required=True)
    parser.add_argument("--expected-proof-header-sha256", required=True)
    parser.add_argument("--expected-proof-source-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
            args.project,
            args.midi,
            args.card_root,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_voice_header_sha256=args.expected_voice_header_sha256,
            expected_player_source_sha256=args.expected_player_source_sha256,
            expected_player_header_sha256=args.expected_player_header_sha256,
            expected_frt_source_sha256=args.expected_frt_source_sha256,
            expected_frt_header_sha256=args.expected_frt_header_sha256,
            expected_stream_source_sha256=args.expected_stream_source_sha256,
            expected_stream_header_sha256=args.expected_stream_header_sha256,
            expected_candidate_main_sha256=args.expected_candidate_main_sha256,
            expected_candidate_menu_sha256=args.expected_candidate_menu_sha256,
            expected_runtime_sha256=args.expected_runtime_sha256,
            expected_proof_header_sha256=args.expected_proof_header_sha256,
            expected_proof_source_sha256=args.expected_proof_source_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KR24PhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-r24-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r24-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    print("SRK R24 real-SMF physical candidate pre-media gate")
    print("--------------------------------------------------")
    print(f"Project                    : {result.project_root}")
    print(f"Source MIDI                : {result.source_midi_path}")
    print(f"Source MIDI SHA-256        : {result.source_midi_sha256}")
    print(f"Manifest SHA-256           : {result.manifest_sha256}")
    print(f"Build report SHA-256       : {result.report_sha256}")
    print(f"Resident image SHA-256     : {result.image_sha256}")
    print(f"Candidate main SHA-256     : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256     : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256      : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256       : {result.proof_header_sha256}")
    print(f"Proof source SHA-256       : {result.proof_source_sha256}")
    print(f"Song records               : {result.song_records}")
    print(f"Song batches               : {result.song_batches}")
    print(f"Song duration              : {result.song_duration_us} us")
    print(f"Expected Note On / Off     : {result.note_on_count} / {result.note_off_count}")
    print(f"Expected peak polyphony    : {result.peak_polyphony}")
    print(f"Summary words verified     : {result.summary_words_verified}")
    print(f"Controller words verified  : {result.controller_words_verified}")
    print(f"Active-note words verified : {result.active_note_words_verified}")
    print("Final read sequence/index  : 10 / 22")
    print("Expected busy/final active : 0 / 0")
    print("Clock backend              : SH-2 FRT /128")
    print("Clock selection            : runtime VDP2 PAL + 320/352 group")
    print("FRT original TCR restore   : REQUIRED on terminal path")
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
    print("Accepted inert chain       : PASS")
    print("Generated representation   : PASS")
    print("Physical proof renderer    : PASS")
    print("310-event song contract    : PASS")
    print("1408-word final state      : PASS")
    print("Externally accepted hashes : PASS")
    print("SAROO destination          : FRESH")
    print("SAROO writes               : NONE")
    print()
    print("Result                     : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
