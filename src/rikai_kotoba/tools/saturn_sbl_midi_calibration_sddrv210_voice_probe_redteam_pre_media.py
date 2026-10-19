from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_redteam_pre_media import (
    SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError,
    audit_sddrv210_voice_probe_redteam_pre_media,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-sddrv210-voice-probe-redteam-pre-media",
        description=(
            "Read-only audit for the REDTEAM-hardened SDDRV210 voice probe. "
            "Performs no SAROO writes."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_sddrv210_voice_probe_redteam_pre_media(args.project)
    except SaturnSblMidiCalibrationSddrv210VoiceProbeRedTeamPreMediaError as exc:
        print("SRK SDDRV210 VOICE-PROBE REDTEAM PRE-MEDIA")
        print("-----------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("SAROO writes              : NONE")
        print("Deployment                : BLOCKED")
        return 1

    print("SRK SDDRV210 VOICE-PROBE REDTEAM PRE-MEDIA")
    print("-----------------------------------------")
    print(f"Project                   : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print(f"Sound driver SHA-256      : {report.sound_driver_sha256}")
    print(f"Deployable BIN            : {report.bin_bytes} bytes SHA-256 {report.bin_sha256}")
    print(f"Deployable CUE            : {report.cue_bytes} bytes SHA-256 {report.cue_sha256}")
    print("Probe access              : UINT16_ALIGNED")
    print("Probe hardening           : R3_REDTEAM")
    print("Allocation flag gate      : REMOVED")
    print("SDDRV slot scan           : INDEPENDENT + LATCHED")
    print("SCSP slot scan            : INDEPENDENT + LATCHED")
    print("32-bit pointer reads      : DOUBLE-SAMPLED")
    print("BANK_init invariant       : 0x007F / BUS sanity")
    print("Probe behavior            : READ ONLY")
    print("SAROO writes              : NONE")
    print("Deployment                : BLOCKED PENDING FINAL HASH LOCK")
    print()
    print("Result                    : SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
