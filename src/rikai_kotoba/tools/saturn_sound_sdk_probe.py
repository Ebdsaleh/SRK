"""CLI for the read-only installed Sega Saturn sound SDK evidence probe."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.sound_sdk_probe import (
    SaturnSoundSdkProbeResult,
    inspect_saturn_sound_sdk,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sound-sdk-probe",
        description=(
            "Read the installed Saturn SDK/sample trees and report exact sound "
            "sequence, tone-bank, PCM and CD-DA API evidence. No SDK files are "
            "copied, modified or executed."
        ),
    )
    parser.add_argument("--saturn-root", required=True, help="Root of the local Saturn-Dev tree")
    parser.add_argument(
        "--match-limit",
        type=int,
        default=240,
        help="Maximum matches retained per evidence class (default: 240)",
    )
    return parser


def _print_paths(title: str, paths) -> None:
    print(title)
    print("-" * len(title))
    if not paths:
        print("  [none]")
    else:
        for path in paths:
            print(f"  {path}")
    print()


def _print_matches(title: str, matches) -> None:
    print(title)
    print("-" * len(title))
    if not matches:
        print("  [none]")
    else:
        for match in matches:
            print(f"{match.path}:{match.line_number}")
            print(f"  {match.line}")
    print()


def _print_result(result: SaturnSoundSdkProbeResult) -> None:
    print("SRK Saturn sound SDK evidence probe")
    print("-----------------------------------")
    print(f"Saturn root      : {result.saturn_root}")
    print("Access policy    : READ-ONLY; no files are created, copied, modified, linked, or executed")
    print(f"Text files read  : {result.text_files_read}")
    print(f"Oversize skipped : {result.oversize_skipped}")
    print()

    _print_paths("Sound-related headers", result.snd_headers)

    print("Sound/CD libraries")
    print("------------------")
    if not result.snd_libraries:
        print("  [none]")
    else:
        for artifact in result.snd_libraries:
            print(f"  {artifact.path}")
            print(f"    size    : {artifact.size}")
            print(f"    SHA-256 : {artifact.sha256}")
    print()

    _print_paths("Installed sound sample directories", result.sound_samples)
    _print_matches("Sequence / MIDI-style API evidence", result.sequence_matches)
    _print_matches("Tone / bank / drum API evidence", result.bank_matches)
    _print_matches("PCM API evidence", result.pcm_matches)
    _print_matches("CD / CD-DA API evidence", result.cdda_matches)

    print("Interpretation")
    print("--------------")
    print("Use the exact installed headers and Sega samples above as the authority for the next SRK backend.")
    print("Do not infer missing APIs and do not treat the current synthetic R26-R28 timbre bank as a fidelity solution.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = inspect_saturn_sound_sdk(args.saturn_root, match_limit=args.match_limit)
    except Exception as exc:
        print(f"srk-saturn-sound-sdk-probe: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
