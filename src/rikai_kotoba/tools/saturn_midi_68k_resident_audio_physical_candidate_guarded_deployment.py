"""CLI for two-phase whole-card guarded deployment of R23 MIDI->SCSP."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentError,
    apply_midi_68k_resident_audio_physical_candidate_guarded_deployment,
    prepare_midi_68k_resident_audio_physical_candidate_guarded_deployment,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-resident-audio-physical-candidate-guarded-deployment",
        description=(
            "Prepare or explicitly apply the R23 MIDI->SCSP physical proof inside "
            "a reviewed whole-card SAROO inventory. Without --apply the card is read only."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-producer-source-sha256", required=True)
    parser.add_argument("--expected-producer-header-sha256", required=True)
    parser.add_argument("--expected-resident-object-sha256", required=True)
    parser.add_argument("--expected-producer-object-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-guard-manifest-sha256", default="")
    parser.add_argument("--confirm", default="")
    return parser


def _shared(args) -> dict[str, object]:
    return {
        "expected_image_sha256": args.expected_image_sha256,
        "expected_resident_source_sha256": args.expected_resident_source_sha256,
        "expected_resident_header_sha256": args.expected_resident_header_sha256,
        "expected_voice_header_sha256": args.expected_voice_header_sha256,
        "expected_producer_source_sha256": args.expected_producer_source_sha256,
        "expected_producer_header_sha256": args.expected_producer_header_sha256,
        "expected_resident_object_sha256": args.expected_resident_object_sha256,
        "expected_producer_object_sha256": args.expected_producer_object_sha256,
        "expected_bin_sha256": args.expected_bin_sha256,
        "expected_cue_sha256": args.expected_cue_sha256,
        "destination_name": args.name,
        "category": args.category,
    }


def _print_pre_media(result) -> None:
    print(f"Candidate manifest        : {result.manifest_sha256}")
    print(f"Candidate build report    : {result.report_sha256}")
    print(f"Audio image SHA-256       : {result.image_sha256}")
    print(f"Accepted BIN SHA-256      : {result.deployable_bin_sha256}")
    print(f"Accepted CUE SHA-256      : {result.deployable_cue_sha256}")
    print(f"Proof records             : {result.proof_records}")
    print(f"Batch split               : {result.batch1_records}+{result.batch2_records}")
    print("Scheduler clocks          : 0 / 15000 / 32000 us")
    print(f"Note On / Off clocks      : {result.note_on_clock_us} / {result.note_off_clock_us} us")
    print(f"Audible hold polls        : {result.audible_hold_polls}")
    print(f"MIDI state words          : {result.summary_words_verified}+{result.controller_words_verified}+{result.active_note_words_verified}")
    print(f"Voice-state words         : {result.voice_words_verified}")
    print("SCSP key-on readback      : REQUIRED")
    print("Audible MIDI-driven note  : REQUIRED PHYSICALLY")
    print("Scheduled Note Off        : REQUIRED")
    print("SCSP key-off readback     : REQUIRED")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.apply:
            result = prepare_midi_68k_resident_audio_physical_candidate_guarded_deployment(
                args.project,
                args.card_root,
                args.guard_manifest,
                **_shared(args),
            )
            print("SRK R23 MIDI->SCSP guarded deployment PREPARE")
            print("----------------------------------------------")
            _print_pre_media(result.pre_media)
            print()
            print(f"Card root                 : {result.guard_inventory.card_root}")
            print(f"Future destination        : {result.pre_media.plan.destination_directory}")
            print(f"Guard manifest            : {result.guard_inventory.manifest_path}")
            print(f"Guard manifest SHA-256    : {result.guard_inventory.manifest_sha256}")
            print(f"Card files                : {result.guard_inventory.file_count}")
            print(f"Card directories          : {result.guard_inventory.directory_count}")
            print(f"Total file bytes          : {result.guard_inventory.total_file_bytes}")
            print(f"Files SHA-256ed           : {result.guard_inventory.hashed_file_count}")
            print("Exact pre-write guard     : MATCH")
            print("SAROO writes              : NONE")
            print()
            print("Result                    : READY FOR EXPLICIT R23 APPLY")
            print("The guard manifest was created off-card. No SD-card file was modified.")
            return 0

        if not args.expected_guard_manifest_sha256:
            raise SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentError(
                "--expected-guard-manifest-sha256 is required with --apply"
            )
        result = apply_midi_68k_resident_audio_physical_candidate_guarded_deployment(
            args.project,
            args.card_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            confirmation=args.confirm,
            **_shared(args),
        )
        print("SRK R23 MIDI->SCSP guarded deployment APPLY")
        print("--------------------------------------------")
        _print_pre_media(result.pre_media)
        print()
        print(f"Guard manifest            : {result.guard_manifest_path}")
        print(f"Guard manifest SHA-256    : {result.guard_manifest_sha256}")
        print("Pre-write whole-card      : MATCH")
        print(f"Destination               : {result.deployment.plan.destination_directory}")
        print(f"Destination BIN           : {result.deployment.destination_bin}")
        print(f"  SHA-256                 : {result.deployment.bin_sha256}")
        print(f"Destination CUE           : {result.deployment.destination_cue}")
        print(f"  SHA-256                 : {result.deployment.cue_sha256}")
        print("Authorised differences    :")
        for relative in result.allowed_changed_paths:
            print(f"  {relative}")
        print("Post-write whole-card     : PASS (only authorised R23 additions differ)")
        print()
        print("Result                    : R23 DEPLOYMENT VERIFIED")
        print("Existing SAROO content was not overwritten or removed.")
        print("Safely eject the SD card before moving it to the Saturn.")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-resident-audio-physical-candidate-guarded-deployment: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
