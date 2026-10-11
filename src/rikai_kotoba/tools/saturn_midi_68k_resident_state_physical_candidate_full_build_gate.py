"""CLI for the Phase-B full-state physical candidate build."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_physical_candidate import (
    build_srk_saturn_midi_68k_resident_state_proof_snapshot,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_physical_candidate_full_build_gate import (
    run_midi_68k_resident_state_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-state-physical-candidate-full-build-gate",
        description=(
            "Derive a fresh off-card Phase-B candidate from the accepted inert "
            "state-decoder tree, bind the 20-record full-state proof, and run "
            "the normal standalone build. No SAROO/card write occurs."
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
        result = run_midi_68k_resident_state_physical_candidate_full_build_gate(
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
            "srk-saturn-midi-68k-resident-state-physical-candidate-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    snapshot = build_srk_saturn_midi_68k_resident_state_proof_snapshot()
    print("SRK Phase-B resident MIDI 68K full-state physical candidate gate")
    print("----------------------------------------------------------------")
    print(f"Accepted inert baseline : {prepared.baseline_root}")
    print(f"Output candidate        : {prepared.output_root}")
    print(f"Baseline manifest SHA   : {prepared.baseline_manifest_sha256}")
    print(f"Baseline report SHA     : {prepared.baseline_report_sha256}")
    print(f"Baseline BIN SHA        : {prepared.baseline_bin_sha256}")
    print(f"Baseline CUE SHA        : {prepared.baseline_cue_sha256}")
    print(f"State image SHA         : {prepared.image_sha256}")
    print(f"Candidate main SHA      : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA      : {prepared.candidate_menu_sha256}")
    print(f"Runtime after SHA       : {prepared.runtime_after_sha256}")
    print(f"Proof records           : {prepared.proof_records}")
    print(f"Proof final time        : {prepared.proof_final_time_us} us")
    print(f"Summary words verified  : {prepared.state_summary_words_verified}")
    print(f"Controller words verify : {prepared.controller_words_verified}")
    print(f"Active-note words verify: {prepared.active_note_words_verified}")
    print("Proof screen            : MIDI 68K State Proof")
    print("Trigger                 : release A, then fresh A press")
    print("PASS requires           : mailbox + RS telemetry + complete state match")
    print("MIDI-driven SCSP note   : NO")
    print("Build-time hardware I/O : NO")
    print("SAROO writes            : NONE")
    print()
    print("Expected visible state")
    print(
        f"  CH3 program/bank      : {snapshot.ch3_program} / "
        f"{snapshot.ch3_bank_msb}:{snapshot.ch3_bank_lsb}"
    )
    print(
        f"  CH3 vol/pan/expression: {snapshot.ch3_volume} / "
        f"{snapshot.ch3_pan} / {snapshot.ch3_expression}"
    )
    print(
        f"  CH3 sustain/pressure  : {snapshot.ch3_sustain} / "
        f"{snapshot.ch3_channel_pressure}"
    )
    print(f"  CH3 pitch bend        : {snapshot.ch3_pitch_bend}")
    print(
        f"  CH3 last note/velocity: {snapshot.ch3_last_note} / "
        f"{snapshot.ch3_last_velocity}"
    )
    print(
        f"  CH3 poly note/pressure: {snapshot.ch3_last_poly_note} / "
        f"{snapshot.ch3_last_poly_pressure}"
    )
    print(
        f"  CH3 active/CC74       : {snapshot.ch3_active_note_count} / "
        f"{snapshot.ch3_cc74}"
    )
    print(
        f"  CH9 program/volume    : {snapshot.ch9_program} / "
        f"{snapshot.ch9_volume}"
    )
    print(
        f"  CH9 pitch/note/active : {snapshot.ch9_pitch_bend} / "
        f"{snapshot.ch9_last_note} / {snapshot.ch9_active_note_count}"
    )
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
            "Do not deploy it before independent pre-media and whole-card guards."
        )
        return 0

    print("Result                 : FAILED")
    print("Preserve the fresh output tree and full console output; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
