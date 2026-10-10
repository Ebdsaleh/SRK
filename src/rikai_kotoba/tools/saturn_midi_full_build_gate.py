"""CLI for SRK's fresh off-card inert MIDI full-build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_full_build_gate import (
    SaturnMidiFullBuildGateError,
    run_inert_midi_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-full-build-gate",
        description=(
            "Derive a fresh project from one successful standalone baseline, inject the "
            "behaviorally inert generated MIDI bridge, and run SRK's normal Python-native "
            "standalone build. No SAROO or Saturn hardware write occurs."
        ),
    )
    parser.add_argument(
        "--baseline-project",
        required=True,
        help="Previously successful SRK standalone project used only as a verified source baseline",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card project directory for the inert MIDI full-build gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_inert_midi_full_build_gate(
            args.baseline_project,
            args.output,
        )
    except (OSError, SaturnMidiFullBuildGateError) as exc:
        print(
            f"srk-saturn-midi-full-build-gate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            f"srk-saturn-midi-full-build-gate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build

    print("SRK inert Saturn MIDI full-build gate")
    print("-------------------------------------")
    print(f"Baseline project : {prepared.baseline_root}")
    print(f"Output project   : {prepared.output_root}")
    print(f"Baseline manifest: {prepared.baseline_manifest_sha256}")
    print(f"MIDI source SHA  : {prepared.bridge_source_sha256}")
    print(f"MIDI header SHA  : {prepared.bridge_header_sha256}")
    print("Bridge active    : NO")
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
    print(f"Log             : {build.log_path}")
    print(f"Report          : {build.report_path}")
    if build.successful:
        print("Result          : SUCCESS")
        print("The complete standalone image built with the inert MIDI bridge compiled and linked in.")
        print("No MIDI hardware launch, SAROO write, Sound RAM write, or SCSP write was performed.")
        return 0

    print("Result          : FAILED")
    print("Preserve this fresh gate tree and its build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
