from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_consolidated_pre_media import (
    EXPECTED_FAMILIES,
    SaturnSblMidiCalibrationConsolidatedPreMediaError,
    audit_consolidated_midi_calibration_pre_media,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-consolidated-pre-media",
        description=(
            "Read-only pre-media audit for the consolidated 128-program Sega "
            "SBL/SDDRV MIDI calibration diagnostic."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_consolidated_midi_calibration_pre_media(args.project)
    except SaturnSblMidiCalibrationConsolidatedPreMediaError as exc:
        print("SRK Sega SBL MIDI calibration / consolidated PRE-MEDIA")
        print("-------------------------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("SAROO writes              : NONE")
        print("Hardware execution        : NONE")
        print("Deployment                : BLOCKED")
        return 1

    print("SRK Sega SBL MIDI calibration / consolidated PRE-MEDIA")
    print("-------------------------------------------------------")
    print(f"Project                   : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print(f"Sound driver SHA-256      : {report.sound_driver_sha256}")
    print(f"SoundFont SHA-256         : {report.soundfont_sha256}")
    print(f"Sega sound SHA-256        : {report.sega_snd_sha256}")
    print(f"External .MP SHA-256      : {report.area_map_sha256}")
    print(f"GM programs               : {report.program_count} / 128 REAL")
    print(f"GM family banks           : {report.family_count} x 8")
    print(f"Largest family bytes      : {report.largest_family_bytes}")
    for family, filename, programs, size, digest in EXPECTED_FAMILIES:
        print(
            f"  {filename}  family={family:02d} programs={programs[0]:03d}-{programs[-1]:03d} "
            f"bytes={size} sha256={digest}"
        )
    print(f"Deployable BIN            : {report.bin_bytes} bytes SHA-256 {report.bin_sha256}")
    print(f"Deployable CUE            : {report.cue_bytes} bytes SHA-256 {report.cue_sha256}")
    print("Build report / manifest   : EXACT BINDING")
    print("Generated-file inventory  : EXACT")
    print("Family-bank inventory     : EXACT / NO PROGRAM GAPS")
    print("GATE3F fidelity policy    : REQUIRED")
    print("SBL lifecycle             : SCREEN-OWNED / DEFERRED")
    print("68K execution telemetry   : COMMAND HISTORY + DRIVER/CPU ERROR")
    print("Raw SCSP Audio Test       : RETAINED")
    print("SND_ChgMix dependency     : ABSENT")
    print("Review persistence        : UNBOUND")
    print("SAROO writes              : NONE")
    print("Hardware execution        : NONE")
    print("Deployment                : BLOCKED")
    print()
    print("Result                    : SUCCESS")
    print("Closure                   : CONSOLIDATED PRE-MEDIA EVIDENCE COMPLETE")
    print("Next step                 : guarded SAROO deployment contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
