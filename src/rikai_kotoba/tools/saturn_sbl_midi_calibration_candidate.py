from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate import (
    SaturnSblMidiCalibrationCandidateError,
    build_saturn_sbl_midi_calibration_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-candidate",
        description=(
            "Build the isolated Sega SBL/SDDRV-backed MIDI Test / GM Calibration "
            "candidate. Generation/building is off-card only and never writes SAROO."
        ),
    )
    parser.add_argument("--baseline-project", required=True, type=Path)
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--melodic-tone-bank", type=Path)
    parser.add_argument("--drum-tone-bank", type=Path)
    parser.add_argument("--sound-driver", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_midi_calibration_candidate(
            args.baseline_project,
            args.saturn_root,
            args.output,
            melodic_tone_bank=args.melodic_tone_bank,
            drum_tone_bank=args.drum_tone_bank,
            sound_driver=args.sound_driver,
        )
    except SaturnSblMidiCalibrationCandidateError as exc:
        print("SRK Sega SBL MIDI calibration candidate")
        print("---------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("Raw SCSP fallback         : REFUSED")
        print("Review persistence        : UNBOUND")
        print("SAROO writes              : NONE")
        return 1

    assets = result.assets
    print("SRK Sega SBL MIDI calibration candidate")
    print("---------------------------------------")
    print(f"Project                   : {result.project_root}")
    print(f"Sound driver              : {assets.sound_driver}")
    print(f"Sound driver SHA-256      : {assets.sound_driver_sha256}")
    print(f"GM melodic bank           : {assets.melodic_tone_bank}")
    print(f"GM melodic SHA-256        : {assets.melodic_tone_bank_sha256}")
    print(f"GM drum bank              : {assets.drum_tone_bank}")
    print(f"GM drum SHA-256           : {assets.drum_tone_bank_sha256}")
    print(f"Sega sound library        : {assets.sega_sound_library}")
    print(f"Sega sound SHA-256        : {assets.sega_sound_library_sha256}")
    print(f"Log                       : {result.build.log_path}")
    print(f"Report                    : {result.build.report_path}")
    print("Artifacts")
    for artifact in result.build.artifacts:
        relative = artifact.path.relative_to(result.project_root)
        print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    print()
    print("Result                    : SUCCESS")
    print("MIDI backend              : SEGA SBL / SDDRV DIRECT MIDI")
    print("Raw SCSP Audio Test       : DISABLED IN THIS CANDIDATE")
    print("Review persistence        : UNBOUND")
    print("SAROO writes              : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
