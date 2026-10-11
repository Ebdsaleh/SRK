"""CLI for the independent read-only R20 resident-decoder pre-media gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_decoder_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-decoder-physical-candidate-pre-media-gate",
        description=(
            "Independently verify the completed R20 seven-record resident-decoder "
            "candidate and produce a read-only SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True, help="Completed R20 candidate project directory")
    parser.add_argument("--card-root", required=True, help="Mounted SAROO SD-card root, inspected read-only")
    parser.add_argument("--name", required=True, help="Fresh SAROO destination directory name")
    parser.add_argument("--category", default=None, help="Existing SAROO/ISO category, such as TEST")
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-compiler-source-sha256", required=True)
    parser.add_argument("--expected-compiler-header-sha256", required=True)
    parser.add_argument("--expected-compiler-object-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
            args.project,
            args.card_root,
            expected_image_sha256=args.expected_image_sha256,
            expected_compiler_source_sha256=args.expected_compiler_source_sha256,
            expected_compiler_header_sha256=args.expected_compiler_header_sha256,
            expected_compiler_object_sha256=args.expected_compiler_object_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-decoder-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-decoder-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    print("SRK R20 resident MIDI 68K seven-record candidate pre-media gate")
    print("--------------------------------------------------------------")
    print(f"Project                 : {result.project_root}")
    print(f"Manifest SHA-256        : {result.manifest_sha256}")
    print(f"Build report SHA-256    : {result.report_sha256}")
    print(f"Decoder image SHA-256   : {result.image_sha256}")
    print(f"Candidate main SHA-256  : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256  : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256   : {result.runtime_after_sha256}")
    for name in sorted(result.seam_sha256):
        print(f"Seam {name:<37}: {result.seam_sha256[name]}")
    print(f"Proof records           : {result.proof_records}")
    print(f"Proof final time        : {result.proof_final_time_us} us")
    print("Proof opcode coverage   : all 7 SRKM v1 opcodes exactly once")
    print("Proof UI/call path      : VERIFIED")
    print("Trigger interlock       : VERIFIED (release A, then fresh A press)")
    print("Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 7 / error 0")
    print("Decoder telemetry       : RD v1 / processed 7 / current 7 / ready 1")
    print("MIDI-driven SCSP note   : NO")
    print()
    print("Read-only SAROO plan")
    print(f"Card root               : {plan.card_root}")
    if plan.category_directory is not None:
        print(f"Category                : {plan.category_directory.name}")
    else:
        print("Category                : none")
    print(f"Destination             : {plan.destination_directory}")
    print(f"Source BIN              : {plan.source_bin}")
    print(f"BIN size                : {plan.bin_size} bytes")
    print(f"BIN SHA-256             : {result.deployable_bin_sha256}")
    print(f"Source CUE              : {plan.source_cue}")
    print(f"CUE size                : {plan.cue_size} bytes")
    print(f"CUE SHA-256             : {result.deployable_cue_sha256}")
    print(f"MODE1 sectors           : {plan.sector_count}")
    print(f"Raw track bytes         : {plan.raw_bytes}")
    print("Fresh MODE1 verification: PASS")
    print("Candidate provenance    : PASS")
    print("Decoder provenance      : PASS")
    print("Seven-record proof      : PASS")
    print("Externally accepted hash: PASS")
    print("SAROO destination       : FRESH")
    print("SAROO writes            : NONE")
    print()
    print("Result                  : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
