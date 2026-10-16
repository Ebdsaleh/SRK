from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate_contract import (
    SaturnSblMidiCalibrationCandidateError,
    build_saturn_sbl_midi_calibration_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-candidate",
        description=(
            "Build the consolidated Sega SBL/SDDRV MIDI Test / GM Calibration "
            "diagnostic with 16 real GM family banks, screen-owned SBL lifecycle, "
            "and live 68K command-history telemetry. Off-card only."
        ),
    )
    parser.add_argument("--baseline-project", required=True, type=Path)
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--soundfont", type=Path)
    parser.add_argument("--sound-driver", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_midi_calibration_candidate(
            args.baseline_project,
            args.saturn_root,
            args.output,
            soundfont=args.soundfont,
            sound_driver=args.sound_driver,
        )
    except SaturnSblMidiCalibrationCandidateError as exc:
        print("SRK Sega SBL MIDI calibration / consolidated")
        print("---------------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("Raw SCSP Audio Test       : RETAINED / SEPARATE OWNERSHIP")
        print("Review persistence        : UNBOUND")
        print("SAROO writes              : NONE")
        return 1

    assets = result.assets
    print("SRK Sega SBL MIDI calibration / consolidated")
    print("---------------------------------------------")
    print(f"Project                   : {result.project_root}")
    print(f"Sound driver              : {assets.sound_driver}")
    print(f"Sound driver SHA-256      : {assets.sound_driver_sha256}")
    print(f"SoundFont                 : {assets.soundfont}")
    print(f"SoundFont SHA-256         : {assets.soundfont_sha256}")
    print(f"Sega sound library        : {assets.sega_sound_library}")
    print(f"Sega sound SHA-256        : {assets.sega_sound_library_sha256}")
    print(f"External .MP SHA-256      : {assets.area_map_sha256}")
    print(f"GM family banks           : {len(result.family_banks.banks)} x 8 programs")
    print(f"GM programs               : {result.family_banks.program_count} real voices")
    print(f"Largest family bytes      : {result.family_banks.max_bank_bytes}")
    for bank in result.family_banks.banks:
        lo = bank.programs[0]
        hi = bank.programs[-1]
        print(
            f"  {bank.filename}  family={bank.family:02d} programs={lo:03d}-{hi:03d} "
            f"bytes={bank.size} sha256={bank.sha256}"
        )
    print(f"Log                       : {result.build.log_path}")
    print(f"Report                    : {result.build.report_path}")
    print("Artifacts")
    for artifact in result.build.artifacts:
        relative = artifact.path.relative_to(result.project_root)
        print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    print()
    print("Result                    : SUCCESS")
    print("MIDI backend              : SEGA SBL / SDDRV DIRECT MIDI")
    print("GM bank model             : 16 REAL FAMILY BANKS / NO PLACEHOLDERS")
    print("Fidelity policy           : GATE3F STATIC-TL + VELOCITY TABLES")
    print("SBL lifecycle             : DEFERRED TO MIDI SCREEN ENTRY / RELEASE ON EXIT")
    print("68K execution telemetry   : COMMAND HISTORY + DRIVER/CPU ERROR STATUS")
    print("Raw SCSP Audio Test       : RETAINED / REINITIALIZED AFTER SBL")
    print("Review persistence        : UNBOUND")
    print("SAROO writes              : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
