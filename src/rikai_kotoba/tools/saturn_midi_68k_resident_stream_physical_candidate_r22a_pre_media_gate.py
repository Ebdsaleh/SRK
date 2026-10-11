"""CLI for independent read-only review of the corrected R22A candidate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a import (
    R22A_CORRECTION_LABEL,
    r22a_selected_state_addresses,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_pre_media_gate import (
    SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaGateError,
    inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-stream-physical-candidate-r22a-pre-media-gate",
        description=(
            "Independently verify the corrected R22A physical candidate and produce "
            "a read-only SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media(
            args.project,
            args.card_root,
            expected_image_sha256=args.expected_image_sha256,
            expected_resident_source_sha256=args.expected_resident_source_sha256,
            expected_resident_header_sha256=args.expected_resident_header_sha256,
            expected_producer_source_sha256=args.expected_producer_source_sha256,
            expected_producer_header_sha256=args.expected_producer_header_sha256,
            expected_resident_object_sha256=args.expected_resident_object_sha256,
            expected_producer_object_sha256=args.expected_producer_object_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KResidentStreamPhysicalCandidateR22APreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-physical-candidate-r22a-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    program_address, pitch_address, active_address = r22a_selected_state_addresses()
    plan = result.plan
    print("SRK R22A resident MIDI 68K stream/scheduler corrected pre-media gate")
    print("-------------------------------------------------------------------")
    print(f"Correction               : {R22A_CORRECTION_LABEL}")
    print("R22 physical evidence    : timing/refill + full-state verifier passed")
    print("R22 false failure        : E014 selected-state capture address seam")
    print(f"Program capture address  : 0x{program_address:08X}")
    print(f"Pitch capture address    : 0x{pitch_address:08X}")
    print(f"Active capture address   : 0x{active_address:08X}")
    print(f"Project                  : {result.project_root}")
    print(f"Manifest SHA-256         : {result.manifest_sha256}")
    print(f"Build report SHA-256     : {result.report_sha256}")
    print(f"Stream image SHA-256     : {result.image_sha256}")
    print(f"Candidate main SHA-256   : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256   : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256    : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256     : {result.proof_header_sha256}")
    print(f"Proof source SHA-256     : {result.proof_source_sha256}")
    print(f"Proof records            : {result.proof_records}")
    print(f"Batch split              : {result.batch1_records}+{result.batch2_records}")
    print(
        "Clock milestones         : "
        f"{result.clock_zero_us} / {result.clock_partial_us} / "
        f"{result.clock_batch1_us} / {result.clock_final_us} us"
    )
    print(f"Summary words verified   : {result.summary_words_verified}")
    print(f"Controller words verified: {result.controller_words_verified}")
    print(f"Active-note words verify : {result.active_note_words_verified}")
    print("Corrected capture proof  : PASS")
    print("32+8 timing/refill proof : PASS")
    print("Full-state proof         : PASS")
    print("MIDI-driven SCSP note    : NO")
    print()
    print("Read-only SAROO plan")
    print(f"Card root                : {plan.card_root}")
    if plan.category_directory is not None:
        print(f"Category                 : {plan.category_directory.name}")
    else:
        print("Category                 : none")
    print(f"Destination              : {plan.destination_directory}")
    print(f"BIN size                 : {plan.bin_size} bytes")
    print(f"BIN SHA-256              : {result.deployable_bin_sha256}")
    print(f"CUE size                 : {plan.cue_size} bytes")
    print(f"CUE SHA-256              : {result.deployable_cue_sha256}")
    print(f"MODE1 sectors            : {plan.sector_count}")
    print(f"Raw track bytes          : {plan.raw_bytes}")
    print("Fresh MODE1 verification : PASS")
    print("Candidate provenance     : PASS")
    print("Compiler provenance      : PASS")
    print("SAROO destination        : FRESH")
    print("SAROO writes             : NONE")
    print()
    print("Result                   : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
