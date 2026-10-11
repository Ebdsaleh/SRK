"""CLI for the independent read-only R22 stream/scheduler pre-media gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate import (
    build_srk_saturn_midi_68k_stream_physical_snapshot,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_stream_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-stream-physical-candidate-pre-media-gate",
        description=(
            "Independently verify the completed R22 32+8 refill/timestamp candidate "
            "and produce a read-only SAROO destination plan."
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
        result = inspect_midi_68k_resident_stream_physical_candidate_pre_media(
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
    except (OSError, SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-stream-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    snapshot = build_srk_saturn_midi_68k_stream_physical_snapshot()
    print("SRK R22 resident MIDI 68K stream/scheduler pre-media gate")
    print("----------------------------------------------------------")
    print(f"Project                 : {result.project_root}")
    print(f"Manifest SHA-256        : {result.manifest_sha256}")
    print(f"Build report SHA-256    : {result.report_sha256}")
    print(f"Stream image SHA-256    : {result.image_sha256}")
    print(f"Candidate main SHA-256  : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256  : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256   : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256    : {result.proof_header_sha256}")
    print(f"Proof source SHA-256    : {result.proof_source_sha256}")
    print(f"Proof records           : {result.proof_records}")
    print(f"Batch split             : {result.batch1_records}+{result.batch2_records}")
    print(
        "Clock milestones        : "
        f"{result.clock_zero_us} / {result.clock_partial_us} / "
        f"{result.clock_batch1_us} / {result.clock_final_us} us"
    )
    print("0us proof               : 0 records / no ACK")
    print("15ms proof              : exactly 15 records / no ACK")
    print("32ms proof              : sequence 1 ACK / 32 records")
    print("Refill at old clock     : 0 new records / sequence 1 retained")
    print("40ms proof              : sequence 2 ACK / 40 total")
    print(f"Summary words verified  : {result.summary_words_verified}")
    print(f"Controller words verify : {result.controller_words_verified}")
    print(f"Active-note words verify: {result.active_note_words_verified}")
    print("Proof UI/call path      : VERIFIED")
    print("Trigger interlock       : VERIFIED (release A, then fresh A press)")
    print("State across refills    : PERSISTENT")
    print("MIDI-driven SCSP note   : NO")
    print()
    print("Expected final visible state")
    print(f"  CC74                  : {snapshot.cc74}")
    print(f"  Program               : {snapshot.program}")
    print(f"  Pitch bend            : {snapshot.pitch_bend}")
    print(f"  Active-note count     : {snapshot.active_note_count}")
    print(f"  Last note / velocity  : {snapshot.final_note} / {snapshot.final_velocity}")
    print(f"  Total records / batches: {snapshot.total_records} / {snapshot.batches}")
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
    print("Compiler provenance     : PASS")
    print("32+8 timing/refill proof: PASS")
    print("Full-state proof        : PASS")
    print("Externally accepted hash: PASS")
    print("SAROO destination       : FRESH")
    print("SAROO writes            : NONE")
    print()
    print("Result                  : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
