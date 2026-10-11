"""CLI for the R23 resident MIDI 68K -> SCSP inert standalone gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_full_build_gate import (
    SaturnMidi68KResidentAudioFullBuildGateError,
    run_midi_68k_resident_audio_full_build_gate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-audio-full-build-gate",
        description=(
            "Derive a fresh off-card standalone tree from the exact accepted R22A "
            "physical candidate, link the compiler-accepted R23 MIDI->SCSP resident "
            "image inertly, preserve the R22A callable proof, and run the normal build."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-baseline-runtime-sha256", required=True)
    parser.add_argument("--expected-baseline-main-sha256", required=True)
    parser.add_argument("--expected-baseline-menu-sha256", required=True)
    parser.add_argument("--expected-baseline-proof-source-sha256", required=True)
    parser.add_argument("--expected-baseline-proof-header-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_midi_68k_resident_audio_full_build_gate(
            args.baseline_project,
            args.output,
            expected_baseline_manifest_sha256=args.expected_baseline_manifest_sha256,
            expected_baseline_report_sha256=args.expected_baseline_report_sha256,
            expected_baseline_bin_sha256=args.expected_baseline_bin_sha256,
            expected_baseline_cue_sha256=args.expected_baseline_cue_sha256,
            expected_baseline_runtime_sha256=args.expected_baseline_runtime_sha256,
            expected_baseline_main_sha256=args.expected_baseline_main_sha256,
            expected_baseline_menu_sha256=args.expected_baseline_menu_sha256,
            expected_baseline_proof_source_sha256=args.expected_baseline_proof_source_sha256,
            expected_baseline_proof_header_sha256=args.expected_baseline_proof_header_sha256,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_voice_header_sha256=args.expected_voice_header_sha256,
            expected_producer_source_sha256=args.expected_producer_source_sha256,
            expected_producer_header_sha256=args.expected_producer_header_sha256,
            expected_resident_object_sha256=args.expected_resident_object_sha256,
            expected_producer_object_sha256=args.expected_producer_object_sha256,
        )
    except (OSError, SaturnMidi68KResidentAudioFullBuildGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK R23 resident MIDI 68K -> SCSP inert full-build gate")
    print("-------------------------------------------------------")
    print(f"Accepted R22A baseline       : {prepared.baseline_root}")
    print(f"Output project               : {prepared.output_root}")
    print(f"R22A manifest SHA-256        : {prepared.baseline_manifest_sha256}")
    print(f"R22A report SHA-256          : {prepared.baseline_report_sha256}")
    print(f"R22A BIN SHA-256             : {prepared.baseline_bin_sha256}")
    print(f"R22A CUE SHA-256             : {prepared.baseline_cue_sha256}")
    print(f"R23 audio image SHA-256      : {prepared.image_sha256}")
    print(f"R23 audio words              : {prepared.image_word_count}")
    print(f"R23 audio bytes              : {prepared.image_byte_size}")
    print(f"Program range                : 0x00004000-0x{prepared.program_end_address:08X}")
    print(f"Resident source SHA          : {prepared.resident_source_sha256}")
    print(f"Resident header SHA          : {prepared.resident_header_sha256}")
    print(f"Voice header SHA             : {prepared.voice_header_sha256}")
    print(f"Producer source SHA          : {prepared.producer_source_sha256}")
    print(f"Producer header SHA          : {prepared.producer_header_sha256}")
    print(f"Resident object SHA          : {prepared.resident_object_sha256}")
    print(f"Producer object SHA          : {prepared.producer_object_sha256}")
    print(f"R22A main SHA                : {prepared.r22a_main_sha256}")
    print(f"R22A menu SHA                : {prepared.r22a_menu_sha256}")
    print(f"Runtime before SHA           : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA            : {prepared.runtime_after_sha256}")
    print("Existing R22A binding        : PRESERVED")
    print("Queue/refill semantics       : R22A-compatible")
    print("Timestamp scheduler          : PRESERVED")
    print("MIDI state semantics         : PRESERVED")
    print("Voice allocator              : slot 0 / monophonic / no steal")
    print("Voice state                  : 0x00002100")
    print("PCM waveform                 : 0x00002000")
    print("Pitch table                  : 0x00002200")
    print("68K SCSP register base       : 0x00100000")
    print("First-note proof             : ch3 note 60 vel 100")
    print("Scheduled hold               : 1000000 us")
    print("Resident audio linked        : YES")
    print("Resident audio installed     : NO")
    print("Resident audio executed      : NO")
    print("Candidate bound              : NO")
    print("MIDI-driven SCSP image       : YES")
    print("MIDI-driven SCSP executed    : NO")
    print("Build-time hardware I/O      : NO")
    print("SAROO writes                 : NONE")
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
    print(f"Log                         : {build.log_path}")
    print(f"Report                      : {build.report_path}")
    if build.successful:
        print("Result                      : SUCCESS")
        print("The R23 audio image is linked but remains unbound, uninstalled and unexecuted.")
        print("The physically accepted R22A proof remains callable and byte-preserved.")
        print("Do not deploy this inert integration image.")
        return 0

    print("Result                      : FAILED")
    print("Preserve the fresh output tree and build evidence; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
