"""CLI for SRK's independent read-only R19 silent-batch pre-media gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_silent_batch_physical_candidate_pre_media_gate import (
    SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError,
    inspect_midi_68k_silent_batch_physical_candidate_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-silent-batch-physical-candidate-pre-media-gate",
        description=(
            "Independently re-open a completed R19 silent 27-record MIDI/68K candidate, "
            "verify its image/manifest/report/runtime provenance and externally accepted "
            "BIN/CUE hashes, then produce a read-only SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True, help="Completed R19 candidate project directory")
    parser.add_argument("--card-root", required=True, help="Mounted SAROO SD-card root, inspected read-only")
    parser.add_argument("--name", required=True, help="Fresh SAROO destination directory name")
    parser.add_argument("--category", default=None, help="Existing SAROO/ISO category, such as TEST")
    parser.add_argument(
        "--expected-image-sha256",
        required=True,
        help="Compiler-accepted 5066-word silent-batch image SHA-256",
    )
    parser.add_argument(
        "--expected-bin-sha256",
        required=True,
        help="R19 deployable BIN SHA-256 independently accepted from build output",
    )
    parser.add_argument(
        "--expected-cue-sha256",
        required=True,
        help="R19 deployable CUE SHA-256 independently accepted from build output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_midi_68k_silent_batch_physical_candidate_pre_media(
            args.project,
            args.card_root,
            expected_image_sha256=args.expected_image_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-silent-batch-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-silent-batch-physical-candidate-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    print("SRK R19 silent 27-record MIDI/68K candidate pre-media gate")
    print("-----------------------------------------------------------")
    print(f"Project                 : {result.project_root}")
    print(f"Manifest SHA-256        : {result.manifest_sha256}")
    print(f"Build report SHA-256    : {result.report_sha256}")
    print(f"Batch image SHA-256     : {result.image_sha256}")
    print(f"Candidate main SHA-256  : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256  : {result.candidate_menu_sha256}")
    print(f"Installer source SHA    : {result.installer_source_sha256}")
    print(f"Installer header SHA    : {result.installer_header_sha256}")
    print(f"Batch runtime source SHA: {result.batch_runtime_source_sha256}")
    print(f"Batch runtime header SHA: {result.batch_runtime_header_sha256}")
    print(f"Proof header SHA-256    : {result.proof_header_sha256}")
    print(f"Runtime after SHA-256   : {result.runtime_after_sha256}")
    print("Proof UI/call path      : VERIFIED")
    print("Trigger interlock       : VERIFIED (release A, then fresh A press)")
    print("Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 27 / error 0")
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
    print("Batch image provenance  : PASS")
    print("Externally accepted hash: PASS")
    print("SAROO destination       : FRESH")
    print("SAROO writes            : NONE")
    print()
    print("Result                  : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
