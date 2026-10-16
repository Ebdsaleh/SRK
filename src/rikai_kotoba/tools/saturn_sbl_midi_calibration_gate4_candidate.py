from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_candidate import (
    SaturnSblMidiCalibrationGate4Error,
    build_saturn_sbl_midi_calibration_gate4_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-gate4-candidate",
        description=(
            "Build GATE4 of the Sega SBL/SDDRV MIDI calibration candidate using "
            "the external Sound Simulator .MP area-map representation proven by "
            "SRK's audible native-sequence hardware path. Off-card only."
        ),
    )
    parser.add_argument("--baseline-project", required=True, type=Path)
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--melodic-tone-bank", required=True, type=Path)
    parser.add_argument("--drum-tone-bank", required=True, type=Path)
    parser.add_argument("--sound-driver", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_midi_calibration_gate4_candidate(
            args.baseline_project,
            args.saturn_root,
            args.output,
            melodic_tone_bank=args.melodic_tone_bank,
            drum_tone_bank=args.drum_tone_bank,
            sound_driver=args.sound_driver,
        )
    except SaturnSblMidiCalibrationGate4Error as exc:
        print("SRK Sega SBL MIDI Calibration GATE4")
        print("-----------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("External .MP area map     : REQUIRED")
        print("Raw SCSP fallback         : REFUSED")
        print("SAROO writes              : NONE")
        return 1

    assets = result.assets
    print("SRK Sega SBL MIDI Calibration GATE4")
    print("-----------------------------------")
    print(f"Project                   : {result.project_root}")
    print(f"Sound driver SHA-256      : {assets.sound_driver_sha256}")
    print(f"GM melodic SHA-256        : {assets.melodic_tone_bank_sha256}")
    print(f"GM drum SHA-256           : {assets.drum_tone_bank_sha256}")
    print(f"sega_snd.a SHA-256        : {assets.sega_sound_library_sha256}")
    print(f"External map bytes        : {result.area_map_bytes}")
    print(f"External map SHA-256      : {result.area_map_sha256}")
    print(f"Sound RAM drum start      : 0x{result.drum_start:X}")
    print(f"Build log                 : {result.build.log_path}")
    print(f"Build report              : {result.build.report_path}")
    print("Artifacts")
    for artifact in result.build.artifacts:
        relative = artifact.path.relative_to(result.project_root)
        print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    print()
    print("Result                    : SUCCESS")
    print("Root-cause probe          : GATE3 MAP REPRESENTATION -> EXTERNAL .MP")
    print("Direct MIDI callbacks     : CONCRETE SND_CtrlDirMidi")
    print("SBL init gate             : REQUIRED BEFORE CALLBACK BIND")
    print("Overall volume            : SND_SetTlVl(15)")
    print("Raw SCSP Audio Test       : DISABLED IN THIS CANDIDATE")
    print("Review persistence        : UNBOUND")
    print("SAROO writes              : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
