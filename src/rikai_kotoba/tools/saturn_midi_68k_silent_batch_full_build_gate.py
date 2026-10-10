"""CLI for the off-card inert full-build integration of SRK's silent 68K batch image."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_full_build_gate import (
    SaturnMidi68KSilentBatchFullBuildGateError,
    run_midi_68k_silent_batch_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-silent-batch-full-build-gate",
        description=(
            "Derive a fresh off-card standalone tree from the exact accepted R18 "
            "candidate, link the reviewed 27-record silent MC68EC000 image as inert "
            "constant data, and run the normal standalone build. R18's existing "
            "binding is preserved. No card deployment or Saturn hardware action occurs."
        ),
    )
    parser.add_argument(
        "--baseline-project",
        required=True,
        help="Exact accepted R18 callable candidate project",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Fresh off-card output project for the inert full-build integration gate",
    )
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_silent_batch_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
            expected_image_sha256=args.expected_image_sha256,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-silent-batch-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build

    print("SRK silent full-batch Saturn MIDI 68K full-build gate")
    print("------------------------------------------------------")
    print(f"Accepted R18 baseline : {prepared.baseline_root}")
    print(f"Output project        : {prepared.output_root}")
    print(f"R18 manifest SHA-256  : {prepared.baseline_manifest_sha256}")
    print(f"R18 report SHA-256    : {prepared.baseline_report_sha256}")
    print(f"Batch image SHA-256   : {prepared.image_sha256}")
    print(f"Batch image words     : {prepared.image_word_count}")
    print(f"Batch image bytes     : {prepared.image_byte_size}")
    print(f"Program range         : 0x{prepared.program_address:08X}-0x{prepared.program_end_address:08X}")
    print(f"Expected records      : {prepared.expected_records}")
    print(f"Generated source SHA  : {prepared.source_sha256}")
    print(f"Generated header SHA  : {prepared.header_sha256}")
    print(f"Runtime before SHA    : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA     : {prepared.runtime_after_sha256}")
    print("Existing R18 binding  : PRESERVED")
    print("Batch program linked  : YES")
    print("Batch program installed: NO")
    print("Batch program executed : NO")
    print("Batch candidate bound  : NO")
    print("MIDI-driven SCSP note  : NO")
    print("Build-time hardware I/O: NO")
    print("SAROO writes           : NONE")
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
            "The standalone image carries the reviewed silent full-batch 68K program, "
            "but the new program remains unbound, uninstalled and unexecuted."
        )
        print(
            "Do not deploy this inert integration image. Preserve the tree and full "
            "console output for review before creating a new physical candidate binding."
        )
        return 0

    print("Result                 : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
