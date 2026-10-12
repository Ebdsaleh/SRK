"""CLI for two-phase whole-card guarded deployment of R24 real-SMF proof."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r24_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError,
    apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment,
    prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r24-physical-candidate-guarded-deployment",
        description=(
            "Prepare or explicitly apply the R24 real-SMF physical candidate inside "
            "a reviewed whole-card SAROO inventory. Without --apply the card is read only."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--midi", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expected-candidate-manifest-sha256", required=True)
    parser.add_argument("--expected-candidate-report-sha256", required=True)
    parser.add_argument("--expected-baseline-manifest-sha256", required=True)
    parser.add_argument("--expected-baseline-report-sha256", required=True)
    parser.add_argument("--expected-baseline-bin-sha256", required=True)
    parser.add_argument("--expected-baseline-cue-sha256", required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--expected-resident-source-sha256", required=True)
    parser.add_argument("--expected-resident-header-sha256", required=True)
    parser.add_argument("--expected-voice-header-sha256", required=True)
    parser.add_argument("--expected-player-source-sha256", required=True)
    parser.add_argument("--expected-player-header-sha256", required=True)
    parser.add_argument("--expected-frt-source-sha256", required=True)
    parser.add_argument("--expected-frt-header-sha256", required=True)
    parser.add_argument("--expected-stream-source-sha256", required=True)
    parser.add_argument("--expected-stream-header-sha256", required=True)
    parser.add_argument("--expected-candidate-main-sha256", required=True)
    parser.add_argument("--expected-candidate-menu-sha256", required=True)
    parser.add_argument("--expected-runtime-sha256", required=True)
    parser.add_argument("--expected-proof-header-sha256", required=True)
    parser.add_argument("--expected-proof-source-sha256", required=True)
    parser.add_argument("--expected-bin-sha256", required=True)
    parser.add_argument("--expected-cue-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-guard-manifest-sha256", default="")
    parser.add_argument("--confirm", default="")
    return parser


def _pre_media_kwargs(args) -> dict[str, object]:
    return {
        "expected_baseline_manifest_sha256": args.expected_baseline_manifest_sha256,
        "expected_baseline_report_sha256": args.expected_baseline_report_sha256,
        "expected_baseline_bin_sha256": args.expected_baseline_bin_sha256,
        "expected_baseline_cue_sha256": args.expected_baseline_cue_sha256,
        "expected_image_sha256": args.expected_image_sha256,
        "expected_resident_source_sha256": args.expected_resident_source_sha256,
        "expected_resident_header_sha256": args.expected_resident_header_sha256,
        "expected_voice_header_sha256": args.expected_voice_header_sha256,
        "expected_player_source_sha256": args.expected_player_source_sha256,
        "expected_player_header_sha256": args.expected_player_header_sha256,
        "expected_frt_source_sha256": args.expected_frt_source_sha256,
        "expected_frt_header_sha256": args.expected_frt_header_sha256,
        "expected_stream_source_sha256": args.expected_stream_source_sha256,
        "expected_stream_header_sha256": args.expected_stream_header_sha256,
        "expected_candidate_main_sha256": args.expected_candidate_main_sha256,
        "expected_candidate_menu_sha256": args.expected_candidate_menu_sha256,
        "expected_runtime_sha256": args.expected_runtime_sha256,
        "expected_proof_header_sha256": args.expected_proof_header_sha256,
        "expected_proof_source_sha256": args.expected_proof_source_sha256,
        "expected_bin_sha256": args.expected_bin_sha256,
        "expected_cue_sha256": args.expected_cue_sha256,
    }


def _print_pre_media(result) -> None:
    print(f"Candidate manifest        : {result.manifest_sha256}")
    print(f"Candidate build report    : {result.report_sha256}")
    print(f"Source MIDI SHA-256       : {result.source_midi_sha256}")
    print(f"Resident image SHA-256    : {result.image_sha256}")
    print(f"Candidate main SHA-256    : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256    : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256     : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256      : {result.proof_header_sha256}")
    print(f"Proof source SHA-256      : {result.proof_source_sha256}")
    print(f"Accepted BIN SHA-256      : {result.deployable_bin_sha256}")
    print(f"Accepted CUE SHA-256      : {result.deployable_cue_sha256}")
    print(f"Song records / batches    : {result.song_records} / {result.song_batches}")
    print(f"Note On / Off             : {result.note_on_count} / {result.note_off_count}")
    print(f"Peak polyphony            : {result.peak_polyphony}")
    print(
        "MIDI state words          : "
        f"{result.summary_words_verified}+{result.controller_words_verified}+"
        f"{result.active_note_words_verified}"
    )
    print("Clock backend             : SH-2 FRT /128 / runtime VDP2 selection")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        common = {
            "expected_candidate_manifest_sha256": args.expected_candidate_manifest_sha256,
            "expected_candidate_report_sha256": args.expected_candidate_report_sha256,
            "destination_name": args.name,
            "category": args.category,
        }
        if not args.apply:
            result = prepare_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
                args.project,
                args.midi,
                args.card_root,
                args.guard_manifest,
                **common,
                **_pre_media_kwargs(args),
            )
            print("SRK R24 real-SMF guarded deployment PREPARE")
            print("-------------------------------------------")
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
            print("Result                    : READY FOR EXPLICIT R24 APPLY")
            print("The guard manifest was created off-card. No SD-card file was modified.")
            return 0

        if not args.expected_guard_manifest_sha256:
            raise SaturnMidi68KR24PhysicalCandidateGuardedDeploymentError(
                "--expected-guard-manifest-sha256 is required with --apply"
            )
        pre_media = _pre_media_kwargs(args)
        pre_media.pop("expected_bin_sha256")
        pre_media.pop("expected_cue_sha256")
        result = apply_saturn_midi_68k_r24_physical_candidate_guarded_deployment(
            args.project,
            args.midi,
            args.card_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            expected_bin_sha256=args.expected_bin_sha256,
            expected_cue_sha256=args.expected_cue_sha256,
            confirmation=args.confirm,
            **common,
            **pre_media,
        )
        print("SRK R24 real-SMF guarded deployment APPLY")
        print("-----------------------------------------")
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
        print("Post-write whole-card     : PASS (only authorised R24 additions differ)")
        print()
        print("Result                    : R24 DEPLOYMENT VERIFIED")
        print("Existing SAROO content was not overwritten or removed.")
        print("Safely eject the SD card before moving it to the Saturn.")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r24-physical-candidate-guarded-deployment: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
