"""CLI for the fresh R23 MIDI-driven SCSP physical candidate full-build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_candidate_prepare import (
    SaturnMidi68KResidentAudioCandidatePrepareError,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_full_build_gate import (
    run_midi_68k_resident_audio_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-audio-physical-candidate-full-build-gate",
        description=(
            "Derive a fresh off-card R23 candidate from the exact inert audio integration, "
            "bind the 32+2 refill/audio proof to the explicit-A diagnostic screen, and run "
            "the normal Saturn standalone build. This command never writes SAROO media."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-baseline-runtime-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_resident_audio_physical_candidate_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_baseline_runtime_sha256=args.expected_baseline_runtime_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_voice_header_sha256=args.expected_voice_header_sha256,
            expected_producer_source_sha256=args.expected_producer_source_sha256,
            expected_producer_header_sha256=args.expected_producer_header_sha256,
            expected_resident_object_sha256=args.expected_resident_object_sha256,
            expected_producer_object_sha256=args.expected_producer_object_sha256,
        )
    except (OSError, SaturnMidi68KResidentAudioCandidatePrepareError) as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK R23 resident MIDI 68K -> SCSP physical candidate full-build gate")
    print("--------------------------------------------------------------------")
    print(f"Accepted inert baseline       : {prepared.baseline_root}")
    print(f"Output project                : {prepared.output_root}")
    print(f"Inert manifest SHA-256        : {prepared.baseline_manifest_sha256}")
    print(f"Inert report SHA-256          : {prepared.baseline_report_sha256}")
    print(f"Inert BIN SHA-256             : {prepared.baseline_bin_sha256}")
    print(f"Inert CUE SHA-256             : {prepared.baseline_cue_sha256}")
    print(f"R23 audio image SHA-256       : {prepared.image_sha256}")
    print(f"Candidate main SHA-256        : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA-256        : {prepared.candidate_menu_sha256}")
    print(f"Runtime after SHA-256         : {prepared.runtime_after_sha256}")
    print(f"Proof header SHA-256          : {prepared.proof_header_sha256}")
    print(f"Proof source SHA-256          : {prepared.proof_source_sha256}")
    print(f"Proof records                 : {prepared.proof_records}")
    print(f"Batch split                   : {prepared.batch1_records}+{prepared.batch2_records}")
    print("Scheduler milestones          : 0 / 15000 / 32000 us")
    print(f"MIDI Note On clock            : {prepared.note_on_clock_us} us")
    print(f"MIDI Note Off clock           : {prepared.note_off_clock_us} us")
    print(f"Audible hold polls            : {prepared.audible_hold_polls}")
    print(f"Summary words verified        : {prepared.state_summary_words_verified}")
    print(f"Controller words verified     : {prepared.controller_words_verified}")
    print(f"Active-note words verified    : {prepared.active_note_words_verified}")
    print(f"Voice-state words verified    : {prepared.voice_words_verified}")
    print("R22A refill/timing semantics  : RE-PROVEN BY CONTRACT")
    print("SCSP slot-0 key-on readback   : REQUIRED")
    print("Audible MIDI-driven note      : REQUIRED PHYSICALLY")
    print("Scheduled Note Off            : REQUIRED")
    print("SCSP slot-0 key-off readback  : REQUIRED")
    print("Build-time hardware I/O       : NO")
    print("SAROO writes                  : NONE")
    print()

    print("Commands")
    for command in build.commands:
        print(f"  [{command.returncode}] {command.label}")
        if command.output.strip():
            for line in command.output.rstrip().splitlines():
                print(f"      {line}")

    print()
    if build.artifacts:
        print("Artifacts")
        for artifact in build.artifacts:
            relative = artifact.path.relative_to(build.project_root)
            print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    else:
        print("Artifacts: [none]")

    print()
    print(f"Log                          : {build.log_path}")
    print(f"Report                       : {build.report_path}")
    if build.successful:
        print("Result                       : SUCCESS")
        print("The R23 behavior is only active after future guarded deployment and explicit A press.")
        print("Do not copy this candidate to SAROO manually. Run an independent pre-media gate next.")
        return 0

    print("Result                       : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
