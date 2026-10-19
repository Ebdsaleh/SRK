from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_keyed_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedGuardedDeploymentError,
    apply_sddrv210_voice_probe_keyed_guarded_deployment,
    prepare_sddrv210_voice_probe_keyed_guarded_deployment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-sddrv210-voice-probe-keyed-guarded-deployment",
        description=(
            "Two-phase whole-card guarded deployment for the SDDRV210 R4 "
            "keyed-state voice probe. Fails closed until final artifact hashes "
            "are hard locked."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-guard-manifest-sha256", default="")
    parser.add_argument("--confirm", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not args.apply:
            result = prepare_sddrv210_voice_probe_keyed_guarded_deployment(
                args.project, args.card_root, args.guard_manifest
            )
            print("SRK SDDRV210 KEYED PROBE GUARDED DEPLOYMENT PREPARE")
            print("--------------------------------------------------")
            print(f"Future destination         : {result.plan.destination_directory}")
            print(f"Guard manifest             : {result.guard_inventory.manifest_path}")
            print(f"Guard manifest SHA-256     : {result.guard_inventory.manifest_sha256}")
            print("Result                     : READY FOR EXPLICIT APPLY")
            print(f"Apply confirmation token   : {CONFIRMATION_TOKEN}")
            return 0

        if not args.expected_guard_manifest_sha256:
            raise SaturnSblMidiCalibrationSddrv210VoiceProbeKeyedGuardedDeploymentError(
                "--expected-guard-manifest-sha256 is required with --apply"
            )

        result = apply_sddrv210_voice_probe_keyed_guarded_deployment(
            args.project,
            args.card_root,
            args.guard_manifest,
            expected_guard_manifest_sha256=args.expected_guard_manifest_sha256,
            confirmation=args.confirm,
        )
        print("SRK SDDRV210 KEYED PROBE GUARDED DEPLOYMENT APPLY")
        print("------------------------------------------------")
        print(f"Destination                : {result.deployment.plan.destination_directory}")
        print(f"Destination BIN SHA-256    : {result.deployment.bin_sha256}")
        print(f"Destination CUE SHA-256    : {result.deployment.cue_sha256}")
        print("Result                     : SDDRV210 KEYED PROBE DEPLOYMENT VERIFIED")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-sbl-midi-calibration-sddrv210-voice-probe-keyed-guarded-deployment: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"Fixed destination          : {DESTINATION_NAME}", file=sys.stderr)
        print("SAROO writes               : NONE unless all guards pass", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
