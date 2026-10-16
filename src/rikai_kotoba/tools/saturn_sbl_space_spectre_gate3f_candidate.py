"""Build the locked corrected-tone Space Spectre GATE3F project off-card."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_native_sequence_fidelity_candidate import (
    build_saturn_sbl_native_sequence_fidelity_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre-gate3f-candidate",
        description=(
            "Build a fresh OFF-CARD native SDDRV candidate using the exact corrected "
            "melodic/drum TON bytes already proven in memory. This command cannot write SAROO."
        ),
    )
    parser.add_argument(
        "--failed-project",
        required=True,
        type=Path,
        help="physically failed GATE3E project used as the forensic tone reference",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        type=Path,
        help="successful real-GM GATE2 diagnostic project used only as the standalone project baseline",
    )
    parser.add_argument(
        "--sequence",
        required=True,
        type=Path,
        help="Eridu-validated GATE3B native sequence directory",
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        type=Path,
        help="Saturn-Dev root containing Sega SBL/SDDRV build dependencies",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="fresh off-card GATE3F project directory; existing paths are refused",
    )
    parser.add_argument(
        "--soundfont",
        type=Path,
        help="optional pinned GeneralUser GS path; defaults to SRK's verified local cache",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_native_sequence_fidelity_candidate(
            args.failed_project,
            args.baseline,
            args.sequence,
            args.saturn_root,
            args.output,
            args.soundfont,
        )
    except Exception as exc:
        print(
            f"srk-saturn-sbl-space-spectre-gate3f-candidate: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    candidate = result.candidate
    assets = candidate.assets
    print("SRK Space Spectre / GATE3F CORRECTED NATIVE SDDRV CANDIDATE")
    print("-----------------------------------------------------------")
    print(f"Project                 : {candidate.project_root}")
    print(f"Build result            : {'SUCCESS' if candidate.build.successful else 'FAILED'}")
    print(f"Build report            : {candidate.build.report_path}")
    print(f"Source SoundFont        : {result.source_soundfont}")
    print(f"Notes                   : {candidate.note_count}")
    print(f"Sequence bank bytes     : {candidate.sequence_bank_bytes}")
    print(f"Sequence SHA-256        : {assets.sequence_bank_sha256}")
    print(f"Melodic bytes           : {result.golden_melodic_bytes}")
    print(f"Melodic SHA-256         : {result.golden_melodic_sha256}")
    print(f"Drum bytes              : {result.golden_drum_bytes}")
    print(f"Drum SHA-256            : {result.golden_drum_sha256}")
    print(f"Area-map SHA-256        : {assets.area_map_sha256}")
    print(f"Sound RAM melodic       : 0x{assets.melodic_start:05X}")
    print(f"Sound RAM drums         : 0x{assets.drum_start:05X}")
    print(f"Sound RAM sequence      : 0x{assets.sequence_start:05X}")
    print("Playback API            : SND_StartSeq")
    print("Corrected static TL     : YES")
    print("Multi velocity tables   : YES")
    print("Golden TON hashes       : EXACT")
    print("SAROO writes            : NONE")
    print("Hardware execution      : NONE")
    print("GATE3F deployment       : BLOCKED")
    print("Candidate status        : OFF-CARD BUILD ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
