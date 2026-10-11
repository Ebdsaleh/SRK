"""CLI for the corrected R22A resident stream/scheduler physical candidate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a import (
    R22A_CORRECTION_LABEL,
    r22a_selected_state_addresses,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_full_build_gate import (
    SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateError,
    run_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-stream-physical-candidate-r22a-full-build-gate",
        description=(
            "Derive a fresh R22A stream/scheduler physical candidate from the accepted "
            "inert integration, correcting only the selected-state capture word/byte addresses."
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
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_baseline_runtime_sha256=args.expected_baseline_runtime_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_producer_source_sha256=args.expected_producer_source_sha256,
            expected_producer_header_sha256=args.expected_producer_header_sha256,
            expected_resident_object_sha256=args.expected_resident_object_sha256,
            expected_producer_object_sha256=args.expected_producer_object_sha256,
        )
    except (OSError, SaturnMidi68KResidentStreamPhysicalCandidateR22AFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-physical-candidate-r22a-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    program_address, pitch_address, active_address = r22a_selected_state_addresses()
    print("SRK R22A resident MIDI 68K stream/scheduler corrected physical candidate")
    print("------------------------------------------------------------------------")
    print(f"Correction                   : {R22A_CORRECTION_LABEL}")
    print("R22 hardware evidence         : timing/refill + 1408-word state verifier passed")
    print("R22 false terminal failure    : E014 selected-state capture seam")
    print(f"Program capture byte address  : 0x{program_address:08X}")
    print(f"Pitch capture byte address    : 0x{pitch_address:08X}")
    print(f"Active capture byte address   : 0x{active_address:08X}")
    print(f"Accepted inert baseline       : {prepared.baseline_root}")
    print(f"Output project                : {prepared.output_root}")
    print(f"Inert manifest SHA-256        : {prepared.baseline_manifest_sha256}")
    print(f"Inert report SHA-256          : {prepared.baseline_report_sha256}")
    print(f"Inert BIN SHA-256             : {prepared.baseline_bin_sha256}")
    print(f"Inert CUE SHA-256             : {prepared.baseline_cue_sha256}")
    print(f"Stream image SHA-256          : {prepared.image_sha256}")
    print(f"Candidate main SHA            : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA            : {prepared.candidate_menu_sha256}")
    print(f"Runtime after SHA             : {prepared.runtime_after_sha256}")
    print(f"Proof records                 : {prepared.proof_records}")
    print(f"Batch split                   : {prepared.batch1_records}+{prepared.batch2_records}")
    print("Clock milestones              : 0 / 15000 / 32000 / 40000 us")
    print("Complete state verification   : 256 + 1024 + 128 words")
    print("Resident stream engine change : NONE")
    print("SH-2 producer change          : NONE")
    print("MIDI-driven SCSP note         : NO")
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
        print("R22A is off-card only. Do not deploy before independent pre-media review.")
        return 0

    print("Result                       : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
