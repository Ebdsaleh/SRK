"""Read-only pre-media audit for the corrected Space Spectre GATE3F project."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_native_sequence_fidelity_pre_media import (
    EXPECTED_DRUM_START,
    EXPECTED_SEQUENCE_START,
    audit_gate3f_pre_media,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-gate3f-pre-media",
        description=(
            "Audit a finished corrected GATE3F project before any media boundary. "
            "This command is read-only and accepts no card/deployment path."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = audit_gate3f_pre_media(args.project)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-gate3f-pre-media: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Space Spectre / GATE3F PRE-MEDIA FIDELITY GATE")
    print("--------------------------------------------------")
    print(f"Project                  : {report.project_root}")
    print(f"Manifest SHA-256          : {report.manifest_sha256}")
    print(f"Build-report SHA-256      : {report.build_report_sha256}")
    print("Report/manifest binding   : EXACT")
    print(f"Melodic SHA-256           : {report.melodic_sha256}")
    print(f"Drum SHA-256              : {report.drum_sha256}")
    print(f"Sequence SHA-256          : {report.sequence_sha256}")
    print(f"Area-map SHA-256          : {report.area_map_sha256}")
    print(f"Sound RAM drums           : 0x{EXPECTED_DRUM_START:05X}")
    print(f"Sound RAM sequence        : 0x{EXPECTED_SEQUENCE_START:05X}")
    print(f"Sound-driver SHA-256      : {report.driver_sha256}")
    print(f"sega_snd.a SHA-256        : {report.sega_snd_sha256}")
    print(f"Deployable BIN bytes      : {report.bin_bytes}")
    print(f"Deployable BIN SHA-256    : {report.bin_sha256}")
    print(f"Deployable CUE bytes      : {report.cue_bytes}")
    print(f"Deployable CUE SHA-256    : {report.cue_sha256}")
    print("Runtime contract          : EXACT")
    print("BIN/CUE vs ISO            : VERIFIED")
    print("SAROO writes              : NONE")
    print("File modifications        : NONE")
    print("Hardware execution        : NONE")
    print("GATE3F deployment         : BLOCKED")
    print()
    print("Closure status            : GATE3F PRE-MEDIA EVIDENCE COMPLETE")
    print("Next step                 : lock BIN/CUE hashes, then build guarded deployment gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
