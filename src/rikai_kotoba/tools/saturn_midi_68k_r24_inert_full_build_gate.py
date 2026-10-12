"""CLI for the R24 real-SMF inert standalone integration gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r24_inert_full_build_gate import (
    SaturnMidi68KR24InertFullBuildGateError,
    run_saturn_midi_68k_r24_inert_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r24-inert-full-build-gate",
        description=(
            "Derive a fresh off-card tree from the exact accepted R23 physical "
            "candidate, preserve its callable proof, link R24 two-voice audio, the "
            "complete 310-event real-SMF player and SH-2 FRT backend inertly, then "
            "run the normal Saturn standalone build."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-r23-image-sha256", required=True)
    parser.add_argument("--expected-r23-resident-source-sha256", required=True)
    parser.add_argument("--expected-r23-resident-header-sha256", required=True)
    parser.add_argument("--expected-r23-voice-header-sha256", required=True)
    parser.add_argument("--expected-r23-producer-source-sha256", required=True)
    parser.add_argument("--expected-r23-producer-header-sha256", required=True)
    parser.add_argument("--expected-r23-proof-source-sha256", required=True)
    parser.add_argument("--expected-r23-proof-header-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r24_inert_full_build_gate(
            args.baseline_project,
            args.midi,
            args.output,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_r23_image_sha256=args.expected_r23_image_sha256,
            expected_r23_resident_source_sha256=args.expected_r23_resident_source_sha256,
            expected_r23_resident_header_sha256=args.expected_r23_resident_header_sha256,
            expected_r23_voice_header_sha256=args.expected_r23_voice_header_sha256,
            expected_r23_producer_source_sha256=args.expected_r23_producer_source_sha256,
            expected_r23_producer_header_sha256=args.expected_r23_producer_header_sha256,
            expected_r23_proof_source_sha256=args.expected_r23_proof_source_sha256,
            expected_r23_proof_header_sha256=args.expected_r23_proof_header_sha256,
        )
    except (OSError, SaturnMidi68KR24InertFullBuildGateError) as exc:
        print(
            f"srk-saturn-midi-68k-r24-inert-full-build-gate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            f"srk-saturn-midi-68k-r24-inert-full-build-gate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK R24 real-SMF MIDI inert full-build gate")
    print("--------------------------------------------")
    print(f"Accepted R23 baseline       : {prepared.baseline_root}")
    print(f"Output project              : {prepared.output_root}")
    print(f"Source MIDI                 : {prepared.source_midi_path}")
    print(f"R23 manifest SHA-256        : {prepared.baseline_manifest_sha256}")
    print(f"R23 report SHA-256          : {prepared.baseline_report_sha256}")
    print(f"R23 BIN SHA-256             : {prepared.baseline_bin_sha256}")
    print(f"R23 CUE SHA-256             : {prepared.baseline_cue_sha256}")
    print(f"R23 image SHA-256           : {prepared.baseline_r23_image_sha256}")
    print(f"Source MIDI SHA-256         : {prepared.source_midi_sha256}")
    print(f"Song records                : {prepared.song_records}")
    print(f"Queue batches               : {prepared.song_batches}")
    print(f"Peak polyphony              : {prepared.peak_polyphony}")
    print(f"R24 image SHA-256           : {prepared.r24_image_sha256}")
    print(f"R24 image words             : {prepared.r24_image_word_count}")
    print(f"R24 image bytes             : {prepared.r24_image_byte_size}")
    print(f"R24 program range           : 0x00004000-0x{prepared.r24_program_end_address:08X}")
    print(f"R24 resident source SHA     : {prepared.resident_source_sha256}")
    print(f"R24 resident header SHA     : {prepared.resident_header_sha256}")
    print(f"R24 voice header SHA        : {prepared.voice_header_sha256}")
    print(f"R24 player source SHA       : {prepared.player_source_sha256}")
    print(f"R24 player header SHA       : {prepared.player_header_sha256}")
    print(f"R24 FRT source SHA          : {prepared.frt_source_sha256}")
    print(f"R24 FRT header SHA          : {prepared.frt_header_sha256}")
    print(f"Runtime before SHA          : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA           : {prepared.runtime_after_sha256}")
    print("Accepted R23 binding        : PRESERVED")
    print("R24 allocator               : SCSP slots 0+1 / no steal")
    print("R24 calibrated pitch        : LINKED")
    print("R24 310-event player        : LINKED / NOT INVOKED")
    print("R24 FRT backend             : LINKED / NOT INVOKED")
    print("Physical clock frequency    : NOT SELECTED")
    print("R24 resident installed      : NO")
    print("R24 resident executed       : NO")
    print("Build-time hardware I/O     : NO")
    print("SAROO writes                : NONE")
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
    print(f"Log                         : {build.log_path}")
    print(f"Report                      : {build.report_path}")
    if build.successful:
        print("Result                      : SUCCESS")
        print("R24 is linked only as inert evidence; R23 remains the callable physical proof.")
        print("Do not deploy this inert integration image.")
        return 0

    print("Result                      : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
