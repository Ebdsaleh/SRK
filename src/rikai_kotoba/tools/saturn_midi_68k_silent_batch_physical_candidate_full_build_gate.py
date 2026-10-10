"""CLI for SRK's silent 27-record MIDI/68K candidate build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_full_build_gate import (
    SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError,
    run_midi_68k_silent_batch_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-deploy-bin-sha256", required=True)
    parser.add_argument("--expected-deploy-cue-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_silent_batch_physical_candidate_full_build_gate(
            args.baseline_project,
            args.output,
            expected_image_sha256=args.expected_image_sha256,
            expected_deploy_bin_sha256=args.expected_deploy_bin_sha256,
            expected_deploy_cue_sha256=args.expected_deploy_cue_sha256,
        )
    except (OSError, SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError) as exc:
        print(f"srk-silent-batch-candidate: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK silent 27-record MIDI/68K candidate full-build gate")
    print("---------------------------------------------------------")
    print(f"Accepted inert baseline : {prepared.baseline_root}")
    print(f"Output candidate        : {prepared.output_root}")
    print(f"Baseline manifest SHA   : {prepared.baseline_manifest_sha256}")
    print(f"Baseline report SHA     : {prepared.baseline_report_sha256}")
    print(f"Candidate main SHA      : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA      : {prepared.candidate_menu_sha256}")
    print(f"Runtime after SHA       : {prepared.runtime_after_sha256}")
    print("Proof screen            : MIDI 68K Batch Proof")
    print("Trigger                 : release A, then fresh A press")
    print("Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 27 / error 0")
    print("MIDI-driven SCSP note   : NO")
    print("SAROO writes            : NONE")
    print()
    for command in build.commands:
        print(f"[{command.returncode}] {command.label}")
    print()
    for artifact in build.artifacts:
        relative = artifact.path.relative_to(build.project_root)
        print(f"{relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    print()
    print(f"Log                    : {build.log_path}")
    print(f"Report                 : {build.report_path}")
    print(f"Result                 : {'SUCCESS' if build.successful else 'FAILED'}")
    return 0 if build.successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
