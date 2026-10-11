"""CLI for the Phase-B resident state-decoder inert standalone build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_full_build_gate import (
    SaturnMidi68KResidentStateDecoderFullBuildGateError,
    run_midi_68k_resident_state_decoder_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-state-decoder-full-build-gate",
        description=(
            "Derive a fresh off-card standalone tree from the physically accepted R20 "
            "candidate, link the compiler-accepted Phase-B dynamic MIDI state decoder "
            "as inert constant data, and run the normal standalone build. The accepted "
            "R20 proof remains callable and unchanged. No card or Saturn hardware action occurs."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-compiler-source-sha256", required=True)
    parser.add_argument("--expected-compiler-header-sha256", required=True)
    parser.add_argument("--expected-compiler-object-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_resident_state_decoder_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_compiler_source_sha256=args.expected_compiler_source_sha256,
            expected_compiler_header_sha256=args.expected_compiler_header_sha256,
            expected_compiler_object_sha256=args.expected_compiler_object_sha256,
        )
    except (OSError, SaturnMidi68KResidentStateDecoderFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-state-decoder-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-state-decoder-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK Phase-B resident MIDI 68K state decoder inert full-build gate")
    print("-----------------------------------------------------------------")
    print(f"Accepted R20 baseline   : {prepared.baseline_root}")
    print(f"Output project          : {prepared.output_root}")
    print(f"R20 manifest SHA-256    : {prepared.baseline_manifest_sha256}")
    print(f"R20 report SHA-256      : {prepared.baseline_report_sha256}")
    print(f"R20 BIN SHA-256         : {prepared.baseline_bin_sha256}")
    print(f"R20 CUE SHA-256         : {prepared.baseline_cue_sha256}")
    print(f"State image SHA-256     : {prepared.image_sha256}")
    print(f"State decoder words     : {prepared.image_word_count}")
    print(f"State decoder bytes     : {prepared.image_byte_size}")
    print(
        f"Program range           : 0x{prepared.program_address:08X}-"
        f"0x{prepared.program_end_address:08X}"
    )
    print("Runtime records         : 1..32")
    print("Dynamic state mutation  : ALL 7 SRKM v1 opcodes")
    print(f"Compiler source SHA     : {prepared.source_sha256}")
    print(f"Compiler header SHA     : {prepared.header_sha256}")
    print(f"Compiler object SHA     : {prepared.compiler_object_sha256}")
    print(f"R20 main SHA            : {prepared.r20_main_sha256}")
    print(f"R20 menu SHA            : {prepared.r20_menu_sha256}")
    print(f"Runtime before SHA      : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA       : {prepared.runtime_after_sha256}")
    print("Existing R20 binding    : PRESERVED")
    print("State decoder linked    : YES")
    print("State decoder installed : NO")
    print("State decoder executed  : NO")
    print("Candidate bound         : NO")
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
    if build.artifacts:
        print("Artifacts")
        for artifact in build.artifacts:
            relative = artifact.path.relative_to(build.project_root)
            print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    else:
        print("Artifacts: [none]")

    print()
    print(f"Log                      : {build.log_path}")
    print(f"Report                   : {build.report_path}")
    if build.successful:
        print("Result                   : SUCCESS")
        print(
            "The complete standalone image carries the Phase-B state engine, but it "
            "remains unbound, uninstalled and unexecuted. The accepted R20 proof is preserved."
        )
        print("Do not deploy this inert integration image.")
        return 0

    print("Result                   : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
