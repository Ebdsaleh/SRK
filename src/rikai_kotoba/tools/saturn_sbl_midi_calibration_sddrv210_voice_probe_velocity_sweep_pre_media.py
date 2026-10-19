from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_velocity_sweep_pre_media import (
    SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError,
    audit_sddrv210_velocity_sweep_pre_media,
)

def build_parser():
    parser=argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-sddrv210-velocity-sweep-pre-media",
        description="Read-only R6 interactive velocity-sweep audit. No SAROO writes.",
    )
    parser.add_argument("--project",required=True,type=Path)
    return parser

def main(argv=None):
    args=build_parser().parse_args(argv)
    try:
        report=audit_sddrv210_velocity_sweep_pre_media(args.project)
    except SaturnSblMidiCalibrationSddrv210VelocitySweepPreMediaError as exc:
        print("SRK SDDRV210 R6 VELOCITY-SWEEP PRE-MEDIA")
        print("----------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("SAROO writes              : NONE")
        print("Deployment                : BLOCKED")
        return 1
    print("SRK SDDRV210 R6 VELOCITY-SWEEP PRE-MEDIA")
    print("----------------------------------------")
    print(f"Project                   : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print(f"Sound driver SHA-256      : {report.sound_driver_sha256}")
    print(f"Deployable BIN            : {report.bin_bytes} bytes SHA-256 {report.bin_sha256}")
    print(f"Deployable CUE            : {report.cue_bytes} bytes SHA-256 {report.cue_sha256}")
    print("Probe chain               : R6 VELOCITY -> R5 LEVEL-SEED -> R4 KEYED")
    print("Velocity default          : 100")
    print("Velocity control          : B/C = -/+ 8, clamped 1..127")
    print("Velocity change           : FORCES NOTE OFF")
    print("CC7 / CC11                : 127 / 127")
    print("Tone banks                : UNCHANGED")
    print("Keyed SCSP telemetry      : PRESERVED / KYONB-GATED")
    print("Direct SCSP writes        : NONE")
    print("SAROO writes              : NONE")
    print("Deployment                : BLOCKED PENDING FINAL HASH LOCK")
    print()
    print("Result                    : SUCCESS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
