"""CLI for the fresh off-card R25 RR physical-calibration full-build gate."""

from __future__ import annotations

import argparse
import sys

from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_full_build_gate import (
    SaturnMidi68KR25RRCalibrationFullBuildGateError,
    run_saturn_midi_68k_r25_rr_calibration_full_build_gate,
)


def _rr(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("RR must be an integer from 0 through 31") from exc
    if parsed < 0 or parsed > 31:
        raise argparse.ArgumentTypeError("RR must be an integer from 0 through 31")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-midi-68k-r25-rr-calibration-full-build-gate",
        description=(
            "Derive a fresh callable R25 release-rate calibration candidate from "
            "the exact accepted R24 physical project and run the normal Saturn "
            "standalone build. This command is off-card only and never writes SAROO."
        ),
    )
    parser.add_argument("--baseline-project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--release-rate", required=True, type=_rr)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_saturn_midi_68k_r25_rr_calibration_full_build_gate(
            args.baseline_project,
            args.output,
            release_rate=args.release_rate,
        )
    except (OSError, SaturnMidi68KR25RRCalibrationFullBuildGateError, RuntimeError) as exc:
        print(
            "srk-saturn-midi-68k-r25-rr-calibration-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            "srk-saturn-midi-68k-r25-rr-calibration-full-build-gate: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    prepared = result.prepared
    build = result.build
    print("SRK R25 RR physical calibration full-build gate")
    print("-----------------------------------------------")
    print(f"Accepted R24 baseline        : {prepared.baseline_root}")
    print(f"Output candidate             : {prepared.output_root}")
    print(f"RR probe                     : {prepared.release_rate}")
    print(f"EG1 / EG2                    : 0x{prepared.eg1_word:04X} / 0x{prepared.eg2_word:04X}")
    print(f"R24 manifest SHA-256         : {prepared.baseline_manifest_sha256}")
    print(f"R24 report SHA-256           : {prepared.baseline_report_sha256}")
    print(f"R24 BIN SHA-256              : {prepared.baseline_bin_sha256}")
    print(f"R24 CUE SHA-256              : {prepared.baseline_cue_sha256}")
    print(f"Calibration image SHA-256    : {prepared.calibration_image_sha256}")
    print(f"Resident source SHA-256      : {prepared.resident_source_sha256}")
    print(f"Resident header SHA-256      : {prepared.resident_header_sha256}")
    print(f"Voice header SHA-256         : {prepared.voice_header_sha256}")
    print(f"Candidate main SHA-256       : {prepared.candidate_main_sha256}")
    print(f"Candidate menu SHA-256       : {prepared.candidate_menu_sha256}")
    print(f"Runtime before SHA-256       : {prepared.runtime_before_sha256}")
    print(f"Runtime after SHA-256        : {prepared.runtime_after_sha256}")
    print(f"Proof header SHA-256         : {prepared.proof_header_sha256}")
    print(f"Proof source SHA-256         : {prepared.proof_source_sha256}")
    print("Calibration note             : A4 / MIDI 69 / velocity 100")
    print("Note On / Off                : 250000 / 1250000 us")
    print("Observation after Note Off   : 2000000 us")
    print("Observation end              : 3250000 us")
    print("Measurement mode             : OPERATOR-OBSERVED AUDIO")
    print("SCSP envelope readback       : NO")
    print("Production RR selected       : NO")
    print("Clock source                 : accepted R24 SH-2 FRT /128")
    print("Physical candidate bound     : YES")
    print("Resident executed in build   : NO")
    print("FRT executed in build        : NO")
    print("SCSP MMIO in build           : NO")
    print("Build-time hardware I/O      : NO")
    print("SAROO writes                 : NONE")
    print()

    print("Commands")
    for command in build.commands:
        print(f"  [{command.returncode}] {command.label}")
        if command.output.strip():
            for line in command.output.rstrip().splitlines():
                print(f"      {line}")

    print()
    if build.artifacts:
        print("Artifacts")
        for artifact in build.artifacts:
            relative = artifact.path.relative_to(build.project_root)
            print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    else:
        print("Artifacts: [none]")

    print()
    print(f"Log                          : {build.log_path}")
    print(f"Report                       : {build.report_path}")
    if build.successful:
        print("Result                       : SUCCESS")
        print("Candidate build is off-card evidence only.")
        print("Do not copy or deploy it to SAROO yet.")
        return 0

    print("Result                       : FAILED")
    print("Preserve the fresh candidate tree for diagnosis; do not deploy it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
