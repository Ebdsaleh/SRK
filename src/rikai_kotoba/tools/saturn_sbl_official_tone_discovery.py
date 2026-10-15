"""CLI for read-only Sega/InVision Saturn tone-bank discovery."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_official_tone_discovery import (
    discover_official_tone_candidates,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-official-tone-discovery",
        description=(
            "Read-only scan of an existing Saturn SDK/DTS tree for Sega SCSPBIN-like "
            "tone-bank assets, prioritising General MIDI/InVision/128-voice candidates."
        ),
    )
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=50)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit < 1:
        print("--limit must be >= 1", file=sys.stderr)
        return 2
    try:
        candidates = discover_official_tone_candidates(args.saturn_root)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-official-tone-discovery: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Saturn / OFFICIAL TONE-BANK DISCOVERY")
    print("-----------------------------------------")
    print(f"Saturn root          : {args.saturn_root}")
    print(f"Candidates           : {len(candidates)}")
    print("SAROO writes         : NONE")
    print("File modifications   : NONE")
    print("Hardware execution   : NONE")
    print("GATE3F deployment    : BLOCKED")
    print()

    if not candidates:
        print("No hinted/SCSPBIN-like tone-bank candidates found.")
        return 0

    for index, candidate in enumerate(candidates[: args.limit], 1):
        print(f"[{index:02d}] score={candidate.score} {'SCSPBIN' if candidate.structurally_valid else 'NAME/PATH MATCH'}")
        print(f"     Path             : {candidate.path}")
        print(f"     Bytes            : {candidate.size}")
        print(f"     SHA-256          : {candidate.sha256}")
        if candidate.structurally_valid:
            print(f"     Voices           : {candidate.voice_count}")
            print(
                "     Tables           : "
                f"MIX=0x{candidate.mixer_offset:04X} VL=0x{candidate.velocity_offset:04X} "
                f"PEG=0x{candidate.peg_offset:04X} PLFO=0x{candidate.plfo_offset:04X}"
            )
        print("     Reasons          : " + ", ".join(candidate.reasons))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
