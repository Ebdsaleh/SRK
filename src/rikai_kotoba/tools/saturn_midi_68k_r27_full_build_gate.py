"""CLI for the off-card R27 Space Spectre fidelity-pass build."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r27_full_build_gate import (
    R27_RELEASE_RATE,
    run_saturn_midi_68k_r27_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r27-fidelity-full-build-gate",
        description=(
            "Build R27 fidelity pass 1 on top of the physically accepted R26 FIX1 "
            "transport path. Off-card only; no SAROO write."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-rate", type=int, default=R27_RELEASE_RATE)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r27_full_build_gate(
            args.baseline_project,
            args.repository_root,
            args.output,
            release_rate=args.release_rate,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r27-fidelity-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    p = result.prepared
    build = result.build
    print("SRK R27 Space Spectre fidelity pass 1 full-build gate")
    print("------------------------------------------------------")
    print("Transport baseline             : R26 FIX1 PHYSICAL PASS")
    print("Transport/scheduler changes    : NONE")
    print("GM family mapping              : 16 x 8-program families")
    print("Space Spectre drums            : 35 kick / 40 snare / 42 hi-hat / 51 cymbal")
    print("Note-On gain                   : velocity + channel volume + expression")
    print("Note-On pan                    : MIDI pan -> SCSP direct-output pan")
    print("Active-voice pitch bend        : DEFERRED")
    print(f"Accepted R24 baseline         : {p.baseline_root}")
    print(f"SRK repository                : {p.repository_root}")
    print(f"Output candidate              : {p.output_root}")
    print(f"Source MIDI SHA-256           : {p.source_midi_sha256}")
    print(f"Records / batches             : {p.record_count} / {p.batch_count}")
    print(f"Duration                      : {p.duration_us} us")
    print(f"Note On / Note Off            : {p.note_on_count} / {p.note_off_count}")
    print(f"Raw peak polyphony            : {p.raw_peak_polyphony}")
    print(f"Host capacity steals          : {p.release_steal_count}")
    print(f"Provisional release rate      : {p.release_rate} (production RR UNSET)")
    print(f"R27 resident image SHA-256    : {p.resident_image_sha256}")
    print(f"R27 resident source SHA-256   : {p.resident_source_sha256}")
    print(f"R27 resident header SHA-256   : {p.resident_header_sha256}")
    print(f"Candidate main SHA-256        : {p.candidate_main_sha256}")
    print(f"Runtime after SHA-256         : {p.runtime_after_sha256}")
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
    print(f"Log                           : {build.log_path}")
    print(f"Report                        : {build.report_path}")
    if build.successful:
        print("Result                        : SUCCESS")
        print("R27 is fresh off-card evidence. Do not deploy until the next relay.")
        return 0
    print("Result                        : FAILED")
    print("Preserve the fresh R27 tree for diagnosis; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
