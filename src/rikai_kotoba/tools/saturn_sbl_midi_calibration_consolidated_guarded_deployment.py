"""CLI for two-phase guarded deployment of consolidated SBL MIDI calibration."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_consolidated_guarded_deployment import (
    CATEGORY,
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError,
    apply_sbl_midi_calibration_consolidated_guarded_deployment,
    prepare_sbl_midi_calibration_consolidated_guarded_deployment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-consolidated-guarded-deployment",
        description=(
            "Prepare or explicitly apply the hash-locked consolidated Sega one-shot "
            "SBL MIDI calibration image inside a reviewed whole-card SAROO inventory. "
            "Without --apply the card is read only and only the requested off-card "
            "guard manifest is created."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-guard-manifest-sha256", default="")
    parser.add_argument("--confirm", default="")
    return parser


def _print_locked_evidence(report) -> None:
    print(f"Locked candidate manifest  : {EXPECTED_MANIFEST_SHA256}")
    print(f"Audited candidate manifest : {report.manifest_sha256}")
    print(f"Locked build report        : {EXPECTED_BUILD_REPORT_SHA256}")
    print(f"Audited build report       : {report.build_report_sha256}")
    print(f"Locked external .MP map    : {EXPECTED_AREA_MAP_SHA256}")
    print(f"Locked deployable BIN      : {EXPECTED_BIN_SHA256}")
    print(f"Locked deployable CUE      : {EXPECTED_CUE_SHA256}")
    print("Sega one-shot order        : EXACT")
    print(f"Fixed SAROO category       : {CATEGORY}")
    print(f"Fixed destination          : {DESTINATION_NAME}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.apply:
            result = prepare_sbl_midi_calibration_consolidated_guarded_deployment(
                args.project,
                args.card_root,
                args.guard_manifest,
            )
            print("SRK SBL MIDI Calibration / Consolidated GUARDED DEPLOYMENT PREPARE")
            print("------------------------------------------------------------------")
            _print_locked_evidence(result.pre_media)
            print()
            print(f"Card root                  : {result.guard_inventory.card_root}")
            print(f"Future destination         : {result.plan.destination_directory}")
            print(f"Guard manifest             : {result.guard_inventory.manifest_path}")
            print(f"Guard manifest SHA-256     : {result.guard_inventory.manifest_sha256}")
            print(f"Card files                 : {result.guard_inventory.file_count}")
            print(f"Card directories           : {result.guard_inventory.directory_count}")
            print(f"Total file bytes           : {result.guard_inventory.total_file_bytes}")
            print(f"Files SHA-256ed            : {result.guard_inventory.hashed_file_count}")
            print("Consolidated pre-media     : EXACT")
            print("128-program family model   : EXACT")
            print("Sega Direct-MIDI one-shot  : EXACT")
            print("Screen-owned SBL lifecycle : EXACT")
            print("Raw SCSP Audio Test        : RETAINED")
            print("68K execution telemetry    : REQUIRED")
            print("Exact pre-write card guard : MATCH")
            print("SAROO writes               : NONE")
            print("Existing content changes   : NONE")
            print()
            print("Result                     : READY FOR EXPLICIT CONSOLIDATED APPLY")
            print(f"Apply confirmation token   : {CONFIRMATION_TOKEN}")
            print("Preserve the guard manifest and SHA-256 for the APPLY step.")
            return 0

        if not args.expected_guard_manifest_sha256:
            raise SaturnSblMidiCalibrationConsolidatedGuardedDeploymentError(
                "--expected-guard-manifest-sha256 is required with --apply"
            )
        result = apply_sbl_midi_calibration_consolidated_guarded_deployment(
            args.project,
            args.card_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            confirmation=args.confirm,
        )
        print("SRK SBL MIDI Calibration / Consolidated GUARDED DEPLOYMENT APPLY")
        print("----------------------------------------------------------------")
        _print_locked_evidence(result.pre_media)
        print()
        print(f"Guard manifest             : {result.guard_manifest_path}")
        print(f"Guard manifest SHA-256     : {result.guard_manifest_sha256}")
        print("Pre-write whole-card       : MATCH")
        print(f"Destination                : {result.deployment.plan.destination_directory}")
        print(f"Destination BIN SHA-256    : {result.deployment.bin_sha256}")
        print(f"Destination CUE SHA-256    : {result.deployment.cue_sha256}")
        print("Authorised differences     :")
        for relative in result.allowed_changed_paths:
            print(f"  {relative}")
        print("Post-write whole-card      : PASS (only authorised additions differ)")
        print()
        print("Result                     : CONSOLIDATED ONE-SHOT DEPLOYMENT VERIFIED")
        print("Existing SAROO content was not overwritten or removed.")
        print("Safely eject the SD card before moving it to the Saturn.")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-sbl-midi-calibration-consolidated-guarded-deployment: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
