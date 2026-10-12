"""CLI for the fresh off-card R24 real-SMF physical candidate build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_full_build_gate import (
    SaturnMidi68KR24PhysicalCandidateFullBuildGateError,
    run_saturn_midi_68k_r24_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r24-physical-candidate-full-build-gate",
        description=(
            "Derive a fresh callable R24 310-event real-MIDI physical candidate "
            "from the exact accepted inert integration and run the normal Saturn "
            "standalone build. This command is off-card only and never writes SAROO."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-baseline-runtime-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-player-source-sha256", required=True)
    parser.add_argument("--expected-player-header-sha256", required=True)
    parser.add_argument("--expected-frt-source-sha256", required=True)
    parser.add_argument("--expected-frt-header-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r24_physical_candidate_full_build_gate(
            args.baseline_project,
            args.midi,
            args.output,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_baseline_runtime_sha256=args.expected_baseline_runtime_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_voice_header_sha256=args.expected_voice_header_sha256,
            expected_player_source_sha256=args.expected_player_source_sha256,
            expected_player_header_sha256=args.expected_player_header_sha256,
            expected_frt_source_sha256=args.expected_frt_source_sha256,
            expected_frt_header_sha256=args.expected_frt_header_sha256,
        )
    except (OSError, SaturnMidi68KR24PhysicalCandidateFullBuildGateError, RuntimeError) as exc:
        print(
            "srk-saturn-midi-68k-r24-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r24-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK R24 real-SMF physical candidate full-build gate")
    print("----------------------------------------------------")
    print(f"Accepted inert baseline      : {prepared.baseline_root}")
    print(f"Output candidate             : {prepared.output_root}")
    print(f"Source MIDI                  : {prepared.source_midi_path}")
    print(f"Inert manifest SHA-256       : {prepared.baseline_manifest_sha256}")
    print(f"Inert report SHA-256         : {prepared.baseline_report_sha256}")
    print(f"Inert BIN SHA-256            : {prepared.baseline_bin_sha256}")
    print(f"Inert CUE SHA-256            : {prepared.baseline_cue_sha256}")
    print(f"R24 resident image SHA-256   : {prepared.image_sha256}")
    print(f"Candidate main SHA-256       : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA-256       : {prepared.candidate_menu_sha256}")
    print(f"Runtime before SHA-256       : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA-256        : {prepared.runtime_after_sha256}")
    print(f"Proof header SHA-256         : {prepared.proof_header_sha256}")
    print(f"Proof source SHA-256         : {prepared.proof_source_sha256}")
    print(f"Song records                 : {prepared.song_records}")
    print(f"Song batches                 : {prepared.song_batches}")
    print(f"Song duration                : {prepared.song_duration_us} us")
    print(f"Summary words verified       : {prepared.state_summary_words_verified}")
    print(f"Controller words verified    : {prepared.controller_words_verified}")
    print(f"Active-note words verified   : {prepared.active_note_words_verified}")
    print("Expected final sequence      : 10")
    print("Expected final index         : 22")
    print("Expected Note On / Off       : 140 / 140")
    print("Expected peak / busy / active: 2 / 0 / 0")
    print("Clock source                 : SH-2 FRT /128")
    print("Clock selection              : runtime VDP2 PAL + 320/352 group")
    print("NTSC A / B                   : 26874100 / 28636400 Hz")
    print("PAL A / B                    : 26687700 / 28437700 Hz")
    print("FRT original TCR restore     : REQUIRED on terminal path")
    print("Physical candidate bound     : YES")
    print("Resident executed in build   : NO")
    print("Player executed in build     : NO")
    print("FRT executed in build        : NO")
    print("SCSP MMIO in build           : NO")
    print("Build-time hardware I/O      : NO")
    print("SAROO writes                 : NONE")
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
        print("Candidate build is off-card evidence only.")
        print("Do not deploy before independent R24 pre-media and whole-card guards.")
        return 0

    print("Result                       : FAILED")
    print("Preserve the fresh candidate tree for diagnosis; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
