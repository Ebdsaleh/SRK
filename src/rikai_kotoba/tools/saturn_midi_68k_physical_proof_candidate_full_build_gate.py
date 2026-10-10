"""CLI for SRK's first callable silent MIDI/68K physical-proof candidate build."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_physical_proof_candidate_full_build_gate import (
    SaturnMidi68KPhysicalProofCandidateFullBuildGateError,
    run_midi_68k_physical_proof_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-physical-proof-candidate-full-build-gate",
        description=(
            "Derive a fresh off-card candidate from a previously successful inert "
            "physical-proof full-build tree, compile the explicit A-triggered silent "
            "MIDI/68K proof path, then run the normal standalone build. This command "
            "has no SAROO/card deployment path."
        ),
    )
    parser.add_argument(
        "--baseline-project",
        required=True,
        help=(
            "Previously successful inert MIDI 68K physical-proof full-build output "
            "used as the immutable accepted baseline"
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card project directory for the callable silent-proof candidate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_physical_proof_candidate_full_build_gate(
            args.baseline_project,
            args.output,
        )
    except (OSError, SaturnMidi68KPhysicalProofCandidateFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-physical-proof-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-physical-proof-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build

    print("SRK Saturn MIDI 68K physical-proof candidate full-build gate")
    print("------------------------------------------------------------")
    print(f"Accepted inert baseline : {prepared.baseline_root}")
    print(f"Output candidate        : {prepared.output_root}")
    print(f"Baseline manifest SHA   : {prepared.baseline_manifest_sha256}")
    print(f"Baseline report SHA     : {prepared.baseline_report_sha256}")
    print(f"Reviewed main SHA       : {prepared.reviewed_main_source_sha256}")
    print(f"Candidate main SHA      : {prepared.candidate_main_sha256}")
    print(f"Reviewed menu SHA       : {prepared.reviewed_menu_source_sha256}")
    print(f"Candidate menu SHA      : {prepared.candidate_menu_sha256}")
    print(f"Proof source SHA        : {prepared.proof_source_sha256}")
    print(f"Proof header SHA        : {prepared.proof_header_sha256}")
    print("Physical proof linked   : YES")
    print("Diagnostic binding      : COMPILED")
    print("Proof screen            : MIDI 68K Silent Proof")
    print("Trigger                 : release A, then fresh A press")
    print("Non-blocking poll       : at most once/frame while RUNNING")
    print("MIDI-driven SCSP note   : NO")
    print("Build-time SMPC command : NO")
    print("Build-time Sound RAM I/O: NO")
    print("Build-time 68K execution: NO")
    print("SAROO writes            : NONE")
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
    print(f"Log                    : {build.log_path}")
    print(f"Report                 : {build.report_path}")
    if build.successful:
        print("Result                 : SUCCESS")
        print(
            "The off-card image contains the explicit silent physical-proof UI and "
            "call path, but this build command executed no Saturn hardware action "
            "and performed no SAROO/card write."
        )
        print(
            "Do not deploy from this command. Preserve the candidate tree and full "
            "console output for the next independent inspection/pre-media gate."
        )
        return 0

    print("Result                 : FAILED")
    print("Preserve this fresh candidate tree and its build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
