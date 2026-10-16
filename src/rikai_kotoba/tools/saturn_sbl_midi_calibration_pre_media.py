"""Read-only pre-media audit for the Sega SBL MIDI calibration candidate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_pre_media import (
    audit_midi_calibration_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-midi-calibration-pre-media",
        description=(
            "Audit a finished Sega SBL MIDI calibration candidate before any media "
            "boundary. This command is read-only and accepts no card/deployment path."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = audit_midi_calibration_pre_media(args.project)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-midi-calibration-pre-media: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Sega SBL MIDI Calibration / PRE-MEDIA GATE")
    print("----------------------------------------------")
    print(f"Project                    : {report.project_root}")
    print(f"Manifest SHA-256            : {report.manifest_sha256}")
    print(f"Build-report SHA-256        : {report.build_report_sha256}")
    print("Report/manifest binding     : EXACT")
    print(f"Sound-driver SHA-256        : {report.sound_driver_sha256}")
    print(f"GM melodic SHA-256          : {report.melodic_sha256}")
    print(f"GM drum SHA-256             : {report.drum_sha256}")
    print(f"Area-map SHA-256            : {report.area_map_sha256}")
    print(f"Sound RAM drum start        : 0x{report.drum_start:05X}")
    print(f"sega_snd.a SHA-256          : {report.sega_snd_sha256}")
    print(f"Deployable BIN bytes        : {report.bin_bytes}")
    print(f"Deployable BIN SHA-256      : {report.bin_sha256}")
    print(f"Deployable CUE bytes        : {report.cue_bytes}")
    print(f"Deployable CUE SHA-256      : {report.cue_sha256}")
    print("Runtime/Direct-MIDI contract: EXACT")
    print("Raw SCSP callbacks          : DISABLED")
    print("BIN/CUE vs ISO              : VERIFIED")
    print("Review persistence          : UNBOUND")
    print("SAROO writes                : NONE")
    print("File modifications          : NONE")
    print("Hardware execution          : NONE")
    print("Deployment                  : BLOCKED")
    print()
    print("Closure status              : CALIBRATION PRE-MEDIA EVIDENCE COMPLETE")
    print("Next step                   : lock deployable hashes in guarded SAROO deployment gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
