"""CLI for explicit reviewed R25 RR16 whole-card deployment."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_guarded_apply import (
    ACCEPTED_GUARD_MANIFEST_SHA256,
    ACCEPTED_PREPARE_RECEIPT_SHA256,
    CONFIRMATION_TOKEN,
    apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r25-rr16-guarded-apply",
        description=(
            "Deploy only the physically reviewed R25 RR16 candidate inside the "
            "exact PREPARE whole-card baseline."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--guard-manifest", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--category", default=None)
    parser.add_argument("--name", required=True)
    parser.add_argument("--confirm", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment(
            args.project,
            args.card_root,
            args.guard_manifest,
            args.receipt,
            destination_name=args.name,
            category=args.category,
            confirmation=args.confirm,
        )
        print("SRK R25 RR16 guarded deployment APPLY")
        print("--------------------------------------")
        print(f"Project                    : {result.pre_media.project_root}")
        print(f"Accepted R24 baseline      : {result.pre_media.baseline_root}")
        print(f"Guard manifest             : {result.guard_manifest_path}")
        print(f"Guard manifest SHA-256     : {result.guard_manifest_sha256}")
        print(f"Preparation receipt        : {result.prepare_receipt_path}")
        print(f"Receipt SHA-256            : {result.prepare_receipt_sha256}")
        print(f"Expected guard SHA-256     : {ACCEPTED_GUARD_MANIFEST_SHA256}")
        print(f"Expected receipt SHA-256   : {ACCEPTED_PREPARE_RECEIPT_SHA256}")
        print("Pre-write whole-card       : MATCH")
        print()
        print(f"Destination                : {result.deployment.plan.destination_directory}")
        print(f"Destination BIN            : {result.deployment.destination_bin}")
        print(f"  SHA-256                  : {result.deployment.bin_sha256}")
        print(f"Destination CUE            : {result.deployment.destination_cue}")
        print(f"  SHA-256                  : {result.deployment.cue_sha256}")
        print("Authorised differences     :")
        for relative in result.allowed_changed_paths:
            print(f"  {relative}")
        print("Post-write whole-card      : PASS (only authorised R25 additions differ)")
        print()
        print("RR / EG1 / EG2             : 16 / 0x001F / 0x3C10")
        print("Measurement mode           : OPERATOR-OBSERVED AUDIO")
        print("SCSP envelope readback     : NO")
        print("Production RR selected     : NO")
        print()
        print("Result                     : R25 RR16 DEPLOYMENT VERIFIED")
        print("Existing SAROO content was not overwritten or removed.")
        print("Safely eject the SD card before moving it to the Saturn.")
        return 0
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r25-rr16-guarded-apply: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
