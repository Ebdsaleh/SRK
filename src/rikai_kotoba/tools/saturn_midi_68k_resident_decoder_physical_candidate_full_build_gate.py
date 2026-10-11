"""CLI for the fresh seven-record resident-decoder physical candidate build."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_full_build_gate import (
    run_midi_68k_resident_decoder_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-decoder-physical-candidate-full-build-gate",
        description=(
            "Derive a fresh off-card standalone candidate from the accepted inert "
            "resident-decoder tree, bind the seven-record all-opcode silent proof, "
            "and run the normal standalone build. No SAROO/card write occurs."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-compiler-source-sha256", required=True)
    parser.add_argument("--expected-compiler-header-sha256", required=True)
    parser.add_argument("--expected-compiler-object-sha256", required=True)
    parser.add_argument("--expected-runtime-after-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_resident_decoder_physical_candidate_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_compiler_source_sha256=args.expected_compiler_source_sha256,
            expected_compiler_header_sha256=args.expected_compiler_header_sha256,
            expected_compiler_object_sha256=args.expected_compiler_object_sha256,
            expected_runtime_after_sha256=args.expected_runtime_after_sha256,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-decoder-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK general resident MIDI 68K seven-record physical candidate full-build gate")
    print("----------------------------------------------------------------------------")
    print(f"Accepted inert baseline : {prepared.baseline_root}")
    print(f"Output candidate        : {prepared.output_root}")
    print(f"Baseline manifest SHA   : {prepared.baseline_manifest_sha256}")
    print(f"Baseline report SHA     : {prepared.baseline_report_sha256}")
    print(f"Baseline BIN SHA        : {prepared.baseline_bin_sha256}")
    print(f"Baseline CUE SHA        : {prepared.baseline_cue_sha256}")
    print(f"Decoder image SHA       : {prepared.image_sha256}")
    print(f"Candidate main SHA      : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA      : {prepared.candidate_menu_sha256}")
    print(f"Runtime after SHA       : {prepared.runtime_after_sha256}")
    print(f"Proof records           : {prepared.proof_records}")
    print(f"Proof final time        : {prepared.proof_final_time_us} us")
    print("Proof opcode coverage   : all 7 SRKM v1 opcodes exactly once")
    print("Proof screen            : MIDI 68K Decoder Proof")
    print("Trigger                 : release A, then fresh A press")
    print("Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 7 / error 0")
    print("Decoder telemetry       : RD v1 / processed 7 / current 7 / ready 1")
    print("MIDI-driven SCSP note   : NO")
    print("Build-time hardware I/O : NO")
    print("SAROO writes            : NONE")
    print()

    print("Commands")
    for command in build.commands:
        print(f"  [{command.returncode}] {command.label}")
        if command.output.strip():
            for line in command.output.rstrip().splitlines():
                print(f"      {line}")

    print()
    print("Artifacts")
    for artifact in build.artifacts:
        relative = artifact.path.relative_to(build.project_root)
        print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")

    print()
    print(f"Log                    : {build.log_path}")
    print(f"Report                 : {build.report_path}")
    if build.successful:
        print("Result                 : SUCCESS")
        print(
            "The candidate is callable only if later deployed and explicitly triggered. "
            "Do not deploy it before an independent pre-media gate."
        )
        return 0

    print("Result                 : FAILED")
    print("Preserve the fresh output tree and full console output; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
