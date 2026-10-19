from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_level_seed_pre_media import (
    SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError,
    audit_sddrv210_level_seed_pre_media,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-sddrv210-level-seed-pre-media",
        description=(
            "Read-only audit for the SDDRV210 R5 Direct-MIDI CC7/CC11 "
            "level-seed probe. Performs no SAROO writes."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_sddrv210_level_seed_pre_media(args.project)
    except SaturnSblMidiCalibrationSddrv210LevelSeedPreMediaError as exc:
        print("SRK SDDRV210 R5 LEVEL-SEED PRE-MEDIA")
        print("-----------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("SAROO writes              : NONE")
        print("Deployment                : BLOCKED")
        return 1

    print("SRK SDDRV210 R5 LEVEL-SEED PRE-MEDIA")
    print("-----------------------------------")
    print(f"Project                   : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print(f"Sound driver SHA-256      : {report.sound_driver_sha256}")
    print(f"Deployable BIN            : {report.bin_bytes} bytes SHA-256 {report.bin_sha256}")
    print(f"Deployable CUE            : {report.cue_bytes} bytes SHA-256 {report.cue_sha256}")
    print("Probe chain               : R5 LEVEL-SEED -> R4 KEYED -> R3 REDTEAM")
    print("Channel Volume            : CC7 = 127")
    print("Expression                : CC11 = 127")
    print("Command order             : TL -> CC7 -> CC11 -> CC32 -> PROGRAM")
    print("Keyed SCSP telemetry      : PRESERVED / KYONB-GATED")
    print("Tone banks                : UNCHANGED")
    print("Dummy sequence            : NONE")
    print("Direct SCSP writes        : NONE")
    print("SAROO writes              : NONE")
    print("Deployment                : BLOCKED PENDING FINAL HASH LOCK")
    print()
    print("Result                    : SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
