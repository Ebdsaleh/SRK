from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_volume_pre_media import (
    SaturnSblMidiCalibrationSddrv210VolumePreMediaError,
    audit_sddrv210_volume_pre_media,
    final_hash_lock_matches,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-sddrv210-volume-pre-media",
        description=(
            "Read-only audit for the SDDRV Ver 2.10 Sega Direct-MIDI one-shot "
            "with live 0..15 master-volume control. Performs no SAROO writes."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_sddrv210_volume_pre_media(args.project)
    except SaturnSblMidiCalibrationSddrv210VolumePreMediaError as exc:
        print("SRK SDDRV210 MASTER-VOLUME PRE-MEDIA")
        print("-----------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("SAROO writes              : NONE")
        print("Deployment                : BLOCKED")
        return 1

    print("SRK SDDRV210 MASTER-VOLUME PRE-MEDIA")
    print("-----------------------------------")
    print(f"Project                   : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print(f"Sound driver SHA-256      : {report.sound_driver_sha256}")
    print(f"Deployable BIN            : {report.bin_bytes} bytes SHA-256 {report.bin_sha256}")
    print(f"Deployable CUE            : {report.cue_bytes} bytes SHA-256 {report.cue_sha256}")
    print("Master volume             : 0..15 / DEFAULT 15")
    print("Volume controls           : DPAD UP +1 / DPAD DOWN -1")
    print("Volume command            : SND_SetTlVl / LIVE")
    print("SDDRV version             : 2.10 / EXACT HASH")
    print("SAROO writes              : NONE")
    if final_hash_lock_matches(report):
        print("Deployment                : FINAL HASH LOCK MATCH / PREPARE ELIGIBLE")
    else:
        print("Deployment                : BLOCKED / FINAL HASH LOCK MISMATCH")
    print()
    print("Result                    : SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
