"""CLI for the continuous MIDI 68K stream-service inert standalone gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_full_build_gate import (
    SaturnMidi68KResidentStreamFullBuildGateError,
    run_midi_68k_resident_stream_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-stream-full-build-gate",
        description=(
            "Derive a fresh off-card standalone tree from physically accepted R21, "
            "link the compiler-accepted continuous MIDI 68K stream/scheduler image "
            "and SH-2 refill/timebase producer inertly, and run the normal standalone build."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
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
        result = run_midi_68k_resident_stream_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
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
    except (OSError, SaturnMidi68KResidentStreamFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK resident MIDI 68K multi-batch/timestamp inert full-build gate")
    print("----------------------------------------------------------------")
    print(f"Accepted R21 baseline        : {prepared.baseline_root}")
    print(f"Output project               : {prepared.output_root}")
    print(f"R21 manifest SHA-256         : {prepared.baseline_manifest_sha256}")
    print(f"R21 report SHA-256           : {prepared.baseline_report_sha256}")
    print(f"R21 BIN SHA-256              : {prepared.baseline_bin_sha256}")
    print(f"R21 CUE SHA-256              : {prepared.baseline_cue_sha256}")
    print(f"Stream image SHA-256         : {prepared.image_sha256}")
    print(f"Stream words                 : {prepared.image_word_count}")
    print(f"Stream bytes                 : {prepared.image_byte_size}")
    print(f"Program range                : 0x00004000-0x{prepared.program_end_address:08X}")
    print("Queue refill                 : 1..32 records per batch")
    print("Sequence service             : strict non-zero 16-bit")
    print("Timestamp scheduler          : YES")
    print("Clock seqlock                : YES")
    print("State across refills         : PERSISTENT")
    print(f"Resident source SHA          : {prepared.resident_source_sha256}")
    print(f"Resident header SHA          : {prepared.resident_header_sha256}")
    print(f"Producer source SHA          : {prepared.producer_source_sha256}")
    print(f"Producer header SHA          : {prepared.producer_header_sha256}")
    print(f"Resident object SHA          : {prepared.resident_object_sha256}")
    print(f"Producer object SHA          : {prepared.producer_object_sha256}")
    print(f"R21 main SHA                 : {prepared.r21_main_sha256}")
    print(f"R21 menu SHA                 : {prepared.r21_menu_sha256}")
    print(f"Runtime before SHA           : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA            : {prepared.runtime_after_sha256}")
    print("Existing R21 binding         : PRESERVED")
    print("Resident stream linked       : YES")
    print("Resident stream installed    : NO")
    print("Resident stream executed     : NO")
    print("Stream producer linked       : YES")
    print("Stream producer invoked      : NO")
    print("Candidate bound              : NO")
    print("MIDI-driven SCSP note        : NO")
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
    print(f"Log                         : {build.log_path}")
    print(f"Report                      : {build.report_path}")
    if build.successful:
        print("Result                      : SUCCESS")
        print("The stream/refill scheduler is linked but remains unbound, uninstalled and unexecuted.")
        print("The physically accepted R21 proof remains callable and byte-preserved.")
        print("Do not deploy this inert integration image.")
        return 0

    print("Result                      : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
