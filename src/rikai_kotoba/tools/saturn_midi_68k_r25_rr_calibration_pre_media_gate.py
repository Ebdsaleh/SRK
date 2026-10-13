"""CLI for independent read-only R25 RR16 calibration pre-media review."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_pre_media_gate import (
    SaturnMidi68KR25RRCalibrationPreMediaGateError,
    inspect_saturn_midi_68k_r25_rr_calibration_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r25-rr-calibration-pre-media-gate",
        description=(
            "Independently revalidate the exact accepted R25 RR16 calibration "
            "candidate and produce only a read-only fresh SAROO destination plan."
        ),
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--card-root", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--category", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
            args.project,
            args.card_root,
            destination_name=args.name,
            category=args.category,
        )
    except (OSError, SaturnMidi68KR25RRCalibrationPreMediaGateError) as exc:
        print(
            "srk-saturn-midi-68k-r25-rr-calibration-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r25-rr-calibration-pre-media-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    plan = result.plan
    print("SRK R25 RR16 calibration candidate pre-media gate")
    print("-------------------------------------------------")
    print(f"Project                    : {result.project_root}")
    print(f"Accepted R24 baseline      : {result.baseline_root}")
    print(f"Manifest SHA-256           : {result.manifest_sha256}")
    print(f"Build report SHA-256       : {result.report_sha256}")
    print(f"Calibration image SHA-256  : {result.calibration_image_sha256}")
    print(f"Candidate main SHA-256     : {result.candidate_main_sha256}")
    print(f"Candidate menu SHA-256     : {result.candidate_menu_sha256}")
    print(f"Runtime after SHA-256      : {result.runtime_after_sha256}")
    print(f"Proof header SHA-256       : {result.proof_header_sha256}")
    print(f"Proof source SHA-256       : {result.proof_source_sha256}")
    print("RR / EG1 / EG2            : 16 / 0x001F / 0x3C10")
    print("Calibration note           : A4 / MIDI 69 / velocity 100")
    print("Note On / Off              : 250000 / 1250000 us")
    print("Observation after Note Off : 2000000 us")
    print("Observation end            : 3250000 us")
    print("Measurement mode           : OPERATOR-OBSERVED AUDIO")
    print("SCSP envelope readback     : NO")
    print("Production RR selected     : NO")
    print("Accepted R24 chain         : PASS")
    print("Generated representation   : PASS")
    print("Main/menu derivation       : PASS")
    print("Runtime reconstruction     : PASS")
    print("Successful build pairing   : PASS")
    print()
    print("Read-only SAROO plan")
    print(f"Card root                  : {plan.card_root}")
    if plan.category_directory is not None:
        print(f"Category                   : {plan.category_directory.name}")
    else:
        print("Category                   : none")
    print(f"Destination                : {plan.destination_directory}")
    print(f"Source BIN                 : {plan.source_bin}")
    print(f"BIN size                   : {plan.bin_size} bytes")
    print(f"BIN SHA-256                : {result.deployable_bin_sha256}")
    print(f"Source CUE                 : {plan.source_cue}")
    print(f"CUE size                   : {plan.cue_size} bytes")
    print(f"CUE SHA-256                : {result.deployable_cue_sha256}")
    print(f"MODE1 sectors              : {result.sector_count}")
    print(f"Raw track bytes            : {result.raw_bytes}")
    print("Fresh MODE1 verification   : PASS")
    print("Externally accepted hashes : PASS")
    print("SAROO destination          : FRESH")
    print("SAROO writes               : NONE")
    print()
    print("Result                     : PRE-MEDIA GATE PASS")
    print("No SD-card files were modified. Do not deploy from this command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
