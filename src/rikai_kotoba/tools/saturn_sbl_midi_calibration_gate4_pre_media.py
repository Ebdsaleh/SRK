from __future__ import annotations

import argparse
from pathlib import Path
import sys

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_pre_media import (
    SaturnSblMidiCalibrationGate4PreMediaError,
    audit_sbl_midi_calibration_gate4_pre_media,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-gate4-pre-media",
        description=(
            "Read-only audit of the SBL MIDI calibration GATE4 candidate. "
            "Verifies the external .MP map, real Sega assets, startup/Direct-MIDI "
            "contract, build provenance and deployable BIN/CUE."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_sbl_midi_calibration_gate4_pre_media(args.project)
    except SaturnSblMidiCalibrationGate4PreMediaError as exc:
        print(
            "srk-saturn-sbl-midi-calibration-gate4-pre-media: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Sega SBL MIDI Calibration GATE4 / PRE-MEDIA")
    print("------------------------------------------------")
    print(f"Project                    : {result.project_root}")
    print(f"Manifest SHA-256            : {result.manifest_sha256}")
    print(f"Build-report SHA-256        : {result.build_report_sha256}")
    print("Report/manifest binding     : EXACT")
    print(f"Sound-driver SHA-256        : {result.sound_driver_sha256}")
    print(f"GM melodic SHA-256          : {result.melodic_sha256}")
    print(f"GM drum SHA-256             : {result.drum_sha256}")
    print(f"sega_snd.a SHA-256          : {result.sega_snd_sha256}")
    print(f"External .MP bytes          : {result.area_map_bytes}")
    print(f"External .MP SHA-256        : {result.area_map_sha256}")
    print(f"Sound RAM drum start        : 0x{result.drum_start:X}")
    print(f"Deployable BIN bytes        : {result.bin_bytes}")
    print(f"Deployable BIN SHA-256      : {result.bin_sha256}")
    print(f"Deployable CUE bytes        : {result.cue_bytes}")
    print(f"Deployable CUE SHA-256      : {result.cue_sha256}")
    print("SBL startup gate            : EXACT")
    print("Direct-MIDI callbacks       : CONCRETE")
    print("Overall volume              : SND_SetTlVl(15)")
    print("Raw SCSP callbacks          : DISABLED")
    print("Review persistence          : UNBOUND")
    print("SAROO writes                : NONE")
    print("File modifications          : NONE")
    print("Hardware execution          : NONE")
    print("Deployment                  : BLOCKED")
    print()
    print("Closure status              : GATE4 PRE-MEDIA EVIDENCE COMPLETE")
    print("Next step                   : lock GATE4 deployable hashes in guarded SAROO gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
