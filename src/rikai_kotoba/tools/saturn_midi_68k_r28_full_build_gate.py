"""CLI for the off-card R28 Space Spectre percussion-fidelity build."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r28_full_build_gate import (
    R28_RELEASE_RATE,
    run_saturn_midi_68k_r28_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r28-space-spectre-percussion-p1-full-build-gate",
        description=(
            "Build R28 percussion fidelity pass 1 off-card. "
            "No SAROO media is written."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-rate", type=int, default=R28_RELEASE_RATE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r28_full_build_gate(
            args.baseline_project,
            args.repository_root,
            args.output,
            release_rate=args.release_rate,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r28-space-spectre-percussion-p1-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    p = result.prepared
    build = result.build
    print("SRK R28 Space Spectre percussion fidelity pass 1 full-build gate")
    print("----------------------------------------------------------------")
    print("Transport baseline             : R26 FIX1 PHYSICAL PASS")
    print("Melodic/mixer baseline         : R27 PHYSICAL PASS / fidelity improved")
    print("Transport/scheduler changes    : NONE")
    print("Percussion source select       : GM note selects source only")
    print("Percussion pitch               : fixed per drum; not GM note-as-pitch")
    print("Percussion loop policy         : proven NORMAL_LOOP -> zero-valued tail")
    print("Kick / snare / hat / cymbal    : transient waveforms")
    print("Active-voice pitch bend        : DEFERRED")
    print(f"Accepted R24 baseline          : {p.baseline_root}")
    print(f"SRK repository                 : {p.repository_root}")
    print(f"Output candidate               : {p.output_root}")
    print(f"Source MIDI SHA-256            : {p.source_midi_sha256}")
    print(f"Records / batches              : {p.record_count} / {p.batch_count}")
    print(f"Duration                       : {p.duration_us} us")
    print(f"Note On / Note Off             : {p.note_on_count} / {p.note_off_count}")
    print(f"Raw peak polyphony             : {p.raw_peak_polyphony}")
    print(f"Host capacity steals           : {p.release_steal_count}")
    print(
        f"Provisional release rate       : {p.release_rate} "
        "(production RR UNSET)"
    )
    print(f"R28 resident image SHA-256     : {p.resident_image_sha256}")
    print(f"R28 resident source SHA-256    : {p.resident_source_sha256}")
    print(f"R28 resident header SHA-256    : {p.resident_header_sha256}")
    print(f"Candidate main SHA-256         : {p.candidate_main_sha256}")
    print(f"Runtime after SHA-256          : {p.runtime_after_sha256}")
    print("Build-time hardware I/O        : NO")
    print("SAROO writes                   : NONE")
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

    print(f"Log                            : {build.log_path}")
    print(f"Report                         : {build.report_path}")
    if build.successful:
        print("Result                         : SUCCESS")
        print("R28 is fresh off-card evidence. Do not deploy until the next relay.")
        return 0

    print("Result                         : FAILED")
    print("Preserve the fresh R28 tree for diagnosis; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
