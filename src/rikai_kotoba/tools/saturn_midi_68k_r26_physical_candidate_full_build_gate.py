"""CLI for the off-card R26 Double Impact / Space Spectre physical build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r26_physical_candidate_full_build_gate import (
    ACCEPTED_R26_RELEASE_RATE,
    SaturnMidi68KR26PhysicalCandidateFullBuildGateError,
    run_saturn_midi_68k_r26_physical_candidate_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r26-space-spectre-full-build-gate",
        description=(
            "Derive the fresh R26 Space Spectre physical candidate from the exact "
            "accepted R24 real-song project and run the normal Saturn standalone "
            "build. Off-card only; this command never writes SAROO."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-rate", type=int, default=ACCEPTED_R26_RELEASE_RATE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r26_physical_candidate_full_build_gate(
            args.baseline_project,
            args.repository_root,
            args.output,
            release_rate=args.release_rate,
        )
    except (OSError, RuntimeError, SaturnMidi68KR26PhysicalCandidateFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-r26-space-spectre-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r26-space-spectre-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    p = result.prepared
    build = result.build
    print("SRK R26 Double Impact / Space Spectre physical full-build gate")
    print("-------------------------------------------------------------")
    print(f"Accepted R24 baseline      : {p.baseline_root}")
    print(f"SRK repository             : {p.repository_root}")
    print(f"Output candidate           : {p.output_root}")
    print(f"Source MIDI SHA-256        : {p.source_midi_sha256}")
    print(f"Records / batches          : {p.record_count} / {p.batch_count}")
    print(f"Duration                   : {p.duration_us} us")
    print(f"Note On / Note Off         : {p.note_on_count} / {p.note_off_count}")
    print(f"Raw peak polyphony         : {p.raw_peak_polyphony}")
    print(f"Release-tail steals        : {p.release_steal_count}")
    print(f"Provisional release rate   : {p.release_rate} (production RR UNSET)")
    print(f"Resident image SHA-256     : {p.resident_image_sha256}")
    print(f"Resident source SHA-256    : {p.resident_source_sha256}")
    print(f"Resident header SHA-256    : {p.resident_header_sha256}")
    print(f"Voice header SHA-256       : {p.voice_header_sha256}")
    print(f"Player source SHA-256      : {p.player_source_sha256}")
    print(f"Player header SHA-256      : {p.player_header_sha256}")
    print(f"Proof source SHA-256       : {p.proof_source_sha256}")
    print(f"Proof header SHA-256       : {p.proof_header_sha256}")
    print(f"Candidate main SHA-256     : {p.candidate_main_sha256}")
    print(f"Candidate menu SHA-256     : {p.candidate_menu_sha256}")
    print(f"Runtime before SHA-256     : {p.runtime_before_sha256}")
    print(f"Runtime after SHA-256      : {p.runtime_after_sha256}")
    print("Clock source               : accepted R24 SH-2 FRT /128")
    print("Final release drain        : REQUIRED BEFORE PASS")
    print("Build-time hardware I/O    : NO")
    print("SAROO writes               : NONE")
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
    print(f"Log                        : {build.log_path}")
    print(f"Report                     : {build.report_path}")
    if build.successful:
        print("Result                     : SUCCESS")
        print("R26 Space Spectre candidate is off-card evidence only.")
        print("Do not deploy to SAROO until the independent pre-media/guard gates exist.")
        return 0
    print("Result                     : FAILED")
    print("Preserve the fresh tree for diagnosis; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
