"""CLI for two-phase whole-card guarded R20 resident-decoder deployment."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KResidentDecoderPhysicalCandidateGuardedDeploymentError,
    apply_midi_68k_resident_decoder_physical_candidate_guarded_deployment,
    prepare_midi_68k_resident_decoder_physical_candidate_guarded_deployment,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-decoder-physical-candidate-guarded-deployment",
        description=(
            "Prepare or explicitly apply SRK's R20 seven-record resident-decoder candidate "
            "inside a reviewed whole-card SAROO inventory. Without --apply the mounted "
            "card is read only and only an off-card guard manifest is created."
        ),
    )
    parser.add_argument("--project", required=True, help="Accepted R20 candidate project")
    parser.add_argument("--card-root", required=True, help="Mounted SAROO SD-card root")
    parser.add_argument(
        "--guard-manifest",
        required=True,
        help="Off-card whole-card inventory manifest; must not be on the SAROO card",
    )
    parser.add_argument("--category", default=None, help="Existing SAROO/ISO category")
    parser.add_argument("--name", required=True, help="Fresh R20 destination directory name")
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-compiler-source-sha256", required=True)
    parser.add_argument("--expected-compiler-header-sha256", required=True)
    parser.add_argument("--expected-compiler-object-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Cross the media-write boundary only after a reviewed prepare-phase manifest",
    )
    parser.add_argument(
        "--expected-guard-manifest-sha256",
        default="",
        help="Required with --apply; exact SHA-256 printed by the prepare phase",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply; must be exactly {CONFIRMATION_TOKEN}",
    )
    return parser


def _print_pre_media(result) -> None:
    print(f"Candidate manifest       : {result.manifest_sha256}")
    print(f"Candidate build report   : {result.report_sha256}")
    print(f"Decoder image SHA-256    : {result.image_sha256}")
    print(f"Accepted BIN SHA-256     : {result.deployable_bin_sha256}")
    print(f"Accepted CUE SHA-256     : {result.deployable_cue_sha256}")
    print("Proof records            : 7")
    print("Proof final time         : 7000 us")
    print("Proof opcode coverage    : all 7 SRKM v1 opcodes exactly once")
    print("Proof UI/call path       : VERIFIED")
    print("Trigger interlock        : VERIFIED (release A, then fresh A press)")
    print("Silent PASS contract     : ACKNOWLEDGED / sequence 1 / index 7 / error 0")
    print("Decoder telemetry        : RD v1 / processed 7 / current 7 / ready 1")
    print("MIDI-driven SCSP note    : NO")


def _shared_kwargs(args) -> dict[str, object]:
    return {
        "expected_image_sha256": args.expected_image_sha256,
        "expected_compiler_source_sha256": args.expected_compiler_source_sha256,
        "expected_compiler_header_sha256": args.expected_compiler_header_sha256,
        "expected_compiler_object_sha256": args.expected_compiler_object_sha256,
        "expected_bin_sha256": args.expected_bin_sha256,
        "expected_cue_sha256": args.expected_cue_sha256,
        "destination_name": args.name,
        "category": args.category,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.apply:
            result = prepare_midi_68k_resident_decoder_physical_candidate_guarded_deployment(
                args.project,
                args.card_root,
                args.guard_manifest,
                **_shared_kwargs(args),
            )
            print("SRK R20 resident MIDI 68K guarded deployment PREPARE")
            print("----------------------------------------------------")
            _print_pre_media(result.pre_media)
            print()
            print(f"Card root                : {result.guard_inventory.card_root}")
            print(f"Future destination       : {result.pre_media.plan.destination_directory}")
            print(f"Guard manifest           : {result.guard_inventory.manifest_path}")
            print(f"Guard manifest SHA-256   : {result.guard_inventory.manifest_sha256}")
            print(f"Card files               : {result.guard_inventory.file_count}")
            print(f"Card directories         : {result.guard_inventory.directory_count}")
            print(f"Total file bytes         : {result.guard_inventory.total_file_bytes}")
            print(f"Files SHA-256ed          : {result.guard_inventory.hashed_file_count}")
            print("Exact pre-write guard    : MATCH")
            print("SAROO writes             : NONE")
            print()
            print("Result                   : READY FOR EXPLICIT R20 APPLY")
            print("The guard manifest was created off-card. No SD-card file was modified.")
            print("Preserve the complete output and review the exact manifest SHA before apply.")
            return 0

        if not args.expected_guard_manifest_sha256:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateGuardedDeploymentError(
                "--expected-guard-manifest-sha256 is required with --apply"
            )

        result = apply_midi_68k_resident_decoder_physical_candidate_guarded_deployment(
            args.project,
            args.card_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            confirmation=args.confirm,
            **_shared_kwargs(args),
        )
        print("SRK R20 resident MIDI 68K guarded deployment APPLY")
        print("--------------------------------------------------")
        _print_pre_media(result.pre_media)
        print()
        print(f"Guard manifest           : {result.guard_manifest_path}")
        print(f"Guard manifest SHA-256   : {result.guard_manifest_sha256}")
        print("Pre-write whole-card     : MATCH")
        print(f"Destination              : {result.deployment.plan.destination_directory}")
        print(f"Destination BIN          : {result.deployment.destination_bin}")
        print(f"  SHA-256                : {result.deployment.bin_sha256}")
        print(f"Destination CUE          : {result.deployment.destination_cue}")
        print(f"  SHA-256                : {result.deployment.cue_sha256}")
        print("Authorised differences   :")
        for relative in result.allowed_changed_paths:
            print(f"  {relative}")
        print("Post-write whole-card    : PASS (only authorised R20 additions differ)")
        print()
        print("Result                   : R20 DEPLOYMENT VERIFIED")
        print("Existing SAROO content was not overwritten or removed.")
        print("Safely eject the SD card before moving it to the Saturn.")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-decoder-physical-candidate-guarded-deployment: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
