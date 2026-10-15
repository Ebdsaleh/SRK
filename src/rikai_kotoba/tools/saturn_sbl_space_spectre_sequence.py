"""Compile the locked Space Spectre MIDI to a native Sega Saturn sequence bank."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_space_spectre_sequence import (
    build_space_spectre_native_sequence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-sequence",
        description=(
            "Convert the complete locked Space Spectre SMF type-1 file into an "
            "uncompressed Sega SDDRV M6 song and one-song Saturn sequence bank. "
            "This is host-only conversion and never writes to SAROO."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_space_spectre_native_sequence(args.output)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-sequence: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Space Spectre / native Sega Saturn sequence conversion")
    print("-----------------------------------------------------------")
    print(f"Output directory     : {result.output_directory}")
    print(f"Source SHA-256       : {result.source_sha256}")
    print(f"SMF format           : {result.format_type}")
    print(f"SMF tracks           : {result.track_count}")
    print(f"Ticks / quarter      : {result.resolution}")
    print(f"Tempo events         : {result.tempo_event_count}")
    print(f"End tick             : {result.end_tick}")
    print(f"Channel events       : {result.channel_event_count}")
    print(f"Notes                : {result.note_count}")
    print(f"M6 song bytes        : {result.song_bytes}")
    print(f"M6 song SHA-256      : {result.song_sha256}")
    print(f"Sequence bank        : {result.bank_path}")
    print(f"Sequence bank bytes  : {result.bank_bytes}")
    print(f"Sequence bank SHA-256: {result.bank_sha256}")
    print(f"Manifest             : {result.manifest_path}")
    print("Playback path        : Sega SDDRV native sequence")
    print("Direct MIDI streaming: NO")
    print("SAROO writes         : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
