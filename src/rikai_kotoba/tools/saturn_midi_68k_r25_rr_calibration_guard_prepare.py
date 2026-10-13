"""CLI for read-only R25 RR16 whole-card guard preparation."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guard_prepare import (
    SaturnMidi68KR25RRCalibrationGuardPrepareError,
    prepare_saturn_midi_68k_r25_rr16_calibration_guard,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r25-rr16-guard-prepare",
        description=(
            "Revalidate the exact accepted R25 RR16 calibration candidate, create "
            "and verify a complete off-card SAROO inventory, and publish an off-card "
            "preparation receipt. This command has no deployment/apply operation."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--name", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = prepare_saturn_midi_68k_r25_rr16_calibration_guard(
            args.project,
            args.card_root,
            args.guard_manifest,
            args.receipt,
            destination_name=args.name,
            category=args.category,
        )
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r25-rr16-guard-prepare: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    pre = result.pre_media
    inv = result.guard_inventory
    print("SRK R25 RR16 whole-card guard PREPARE")
    print("-------------------------------------")
    print(f"Project                    : {pre.project_root}")
    print(f"Accepted R24 baseline      : {pre.baseline_root}")
    print(f"Candidate manifest SHA-256 : {pre.manifest_sha256}")
    print(f"Build report SHA-256       : {pre.report_sha256}")
    print(f"Calibration image SHA-256  : {pre.calibration_image_sha256}")
    print(f"Candidate main SHA-256     : {pre.candidate_main_sha256}")
    print(f"Candidate menu SHA-256     : {pre.candidate_menu_sha256}")
    print(f"Runtime after SHA-256      : {pre.runtime_after_sha256}")
    print(f"Proof header SHA-256       : {pre.proof_header_sha256}")
    print(f"Proof source SHA-256       : {pre.proof_source_sha256}")
    print(f"Accepted BIN SHA-256       : {pre.deployable_bin_sha256}")
    print(f"Accepted CUE SHA-256       : {pre.deployable_cue_sha256}")
    print("RR / EG1 / EG2             : 16 / 0x001F / 0x3C10")
    print("Measurement mode           : OPERATOR-OBSERVED AUDIO")
    print("SCSP envelope readback     : NO")
    print("Production RR selected     : NO")
    print(f"Future destination         : {pre.plan.destination_directory}")
    print()
    print("Whole-card guard")
    print(f"Card root                  : {inv.card_root}")
    print(f"Guard manifest             : {inv.manifest_path}")
    print(f"Guard manifest SHA-256     : {inv.manifest_sha256}")
    print(f"Card files                 : {inv.file_count}")
    print(f"Card directories           : {inv.directory_count}")
    print(f"Total file bytes           : {inv.total_file_bytes}")
    print(f"Files SHA-256ed            : {inv.hashed_file_count}")
    print("Exact final guard          : MATCH")
    print()
    print("Bound preparation receipt")
    print(f"Receipt                    : {result.receipt_path}")
    print(f"Receipt SHA-256            : {result.receipt_sha256}")
    print("Candidate/card binding     : PASS")
    print("Destination freshness      : PASS")
    print("SAROO writes               : NONE")
    print("Apply path in this command : NONE")
    print()
    print("Result                     : R25 RR16 PREPARE PASS")
    print("Both guard files were created off-card. No SD-card file was modified.")
    print("Do not deploy yet; the reviewed APPLY gate is a separate future tranche.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
