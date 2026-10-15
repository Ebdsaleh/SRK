"""Build the physical-candidate project for native SDDRV Space Spectre playback."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_native_sequence_candidate import (
    build_saturn_sbl_native_sequence_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-native-candidate",
        description=(
            "Build a fresh Saturn diagnostic candidate that loads the real GM tone "
            "banks plus SPACESEQ.BNK and starts Space Spectre with Sega SDDRV "
            "SND_StartSeq. This build is off-card only."
        ),
    )
    parser.add_argument("--baseline", required=True, type=Path,
                        help="successful real-GM GATE2 diagnostic project")
    parser.add_argument("--sequence", required=True, type=Path,
                        help="fresh v2 native Space Spectre sequence directory")
    parser.add_argument("--saturn-root", required=True, type=Path,
                        help="Saturn-Dev root containing the Sega SBL installation")
    parser.add_argument("--output", required=True, type=Path,
                        help="fresh output project; existing paths are refused")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_native_sequence_candidate(
            args.baseline,
            args.sequence,
            args.saturn_root,
            args.output,
        )
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-native-candidate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    a = result.assets
    print("SRK Space Spectre / native SDDRV physical candidate")
    print("----------------------------------------------------")
    print(f"Project              : {result.project_root}")
    print(f"Build result         : {'SUCCESS' if result.build.successful else 'FAILED'}")
    print(f"Build report         : {result.build.report_path}")
    print(f"Notes                : {result.note_count}")
    print(f"Sequence bank bytes  : {result.sequence_bank_bytes}")
    print(f"Sequence SHA-256     : {a.sequence_bank_sha256}")
    print(f"Melodic SHA-256      : {a.melodic_tone_bank_sha256}")
    print(f"Drum SHA-256         : {a.drum_tone_bank_sha256}")
    print(f"Area-map bytes       : 26")
    print(f"Area-map SHA-256     : {a.area_map_sha256}")
    print(f"Sound RAM melodic    : 0x{a.melodic_start:05X}")
    print(f"Sound RAM drums      : 0x{a.drum_start:05X}")
    print(f"Sound RAM sequence   : 0x{a.sequence_start:05X}")
    print("Playback API         : SND_StartSeq")
    print("Sequence status      : SND_GetSeqStat")
    print("Direct MIDI streaming: NO")
    print("SH-2 event scheduler : NO")
    print("SAROO writes         : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
