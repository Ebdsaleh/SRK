"""CLI for the independent read-only Phase-B full-state pre-media gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_physical_candidate import (
    build_srk_saturn_midi_68k_resident_state_proof_snapshot,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError,
    inspect_midi_68k_resident_state_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-state-physical-candidate-pre-media-gate",
        description=(
            "Independently verify the completed Phase-B full-state candidate and "
            "produce a read-only SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
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
        result = inspect_midi_68k_resident_state_physical_candidate_pre_media(
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
    except (OSError, SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-resident-state-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-state-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    snapshot = build_srk_saturn_midi_68k_resident_state_proof_snapshot()
    print("SRK Phase-B resident MIDI 68K full-state candidate pre-media gate")
    print("----------------------------------------------------------------")
    print(f"Project                 : {result.project_root}")
    print(f"Manifest SHA-256        : {result.manifest_sha256}")
    print(f"Build report SHA-256    : {result.report_sha256}")
    print(f"State image SHA-256     : {result.image_sha256}")
    print(f"Candidate main SHA-256  : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256  : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256   : {result.runtime_after_sha256}")
    for name in sorted(result.seam_sha256):
        print(f"Seam {name:<43}: {result.seam_sha256[name]}")
    print(f"Proof records           : {result.proof_records}")
    print(f"Proof final time        : {result.proof_final_time_us} us")
    print(f"Summary words verified  : {result.summary_words_verified}")
    print(f"Controller words verify : {result.controller_words_verified}")
    print(f"Active-note words verify: {result.active_note_words_verified}")
    print("Proof UI/call path      : VERIFIED")
    print("Trigger interlock       : VERIFIED (release A, then fresh A press)")
    print("PASS contract           : mailbox + RS telemetry + complete state match")
    print("MIDI-driven SCSP note   : NO")
    print()
    print("Expected visible state")
    print(
        f"  CH3 program/bank      : {snapshot.ch3_program} / "
        f"{snapshot.ch3_bank_msb}:{snapshot.ch3_bank_lsb}"
    )
    print(
        f"  CH3 vol/pan/expression: {snapshot.ch3_volume} / "
        f"{snapshot.ch3_pan} / {snapshot.ch3_expression}"
    )
    print(
        f"  CH3 sustain/pressure  : {snapshot.ch3_sustain} / "
        f"{snapshot.ch3_channel_pressure}"
    )
    print(f"  CH3 pitch bend        : {snapshot.ch3_pitch_bend}")
    print(
        f"  CH3 last note/velocity: {snapshot.ch3_last_note} / "
        f"{snapshot.ch3_last_velocity}"
    )
    print(
        f"  CH3 poly note/pressure: {snapshot.ch3_last_poly_note} / "
        f"{snapshot.ch3_last_poly_pressure}"
    )
    print(
        f"  CH3 active/CC74       : {snapshot.ch3_active_note_count} / "
        f"{snapshot.ch3_cc74}"
    )
    print(
        f"  CH9 program/volume    : {snapshot.ch9_program} / "
        f"{snapshot.ch9_volume}"
    )
    print(
        f"  CH9 pitch/note/active : {snapshot.ch9_pitch_bend} / "
        f"{snapshot.ch9_last_note} / {snapshot.ch9_active_note_count}"
    )
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
    print("State provenance        : PASS")
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
