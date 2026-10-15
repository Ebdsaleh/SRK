from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_gm_physical_candidate import (
    SaturnSblGmCandidateError,
    build_saturn_sbl_gm_candidate,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-gm-candidate",
        description=(
            "Build the real Sega Sound Driver + Direct MIDI Space Spectre candidate. "
            "Uses external GM instrument and drum tone banks; never synthetic SRK timbres."
        ),
    )
    parser.add_argument("--baseline-project", required=True, type=Path)
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--melodic-tone-bank", type=Path)
    parser.add_argument("--drum-tone-bank", type=Path)
    parser.add_argument("--sound-driver", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_saturn_sbl_gm_candidate(
            args.baseline_project,
            args.saturn_root,
            args.output,
            melodic_tone_bank=args.melodic_tone_bank,
            drum_tone_bank=args.drum_tone_bank,
            sound_driver=args.sound_driver,
        )
    except SaturnSblGmCandidateError as exc:
        print("SRK Sega Direct MIDI / real GM candidate")
        print("----------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("Synthetic fallback        : REFUSED")
        print("SAROO writes              : NONE")
        return 1

    a = result.assets
    print("SRK Sega Direct MIDI / real GM candidate")
    print("----------------------------------------")
    print(f"Project                   : {result.project_root}")
    print(f"Space Spectre records     : {result.record_count}")
    print(f"Duration us               : {result.duration_us}")
    print(f"Sound driver              : {a.sound_driver}")
    print(f"Sound driver SHA-256      : {a.sound_driver_sha256}")
    print(f"GM instrument bank        : {a.melodic_tone_bank}")
    print(f"GM instrument SHA-256     : {a.melodic_tone_bank_sha256}")
    print(f"GM drum bank              : {a.drum_tone_bank}")
    print(f"GM drum bank SHA-256      : {a.drum_tone_bank_sha256}")
    print(f"Sega sound library        : {a.sega_sound_library}")
    print(f"Sega sound library SHA-256: {a.sega_sound_library_sha256}")
    print(f"Log                       : {result.build.log_path}")
    print(f"Report                    : {result.build.report_path}")
    print("Artifacts")
    for artifact in result.build.artifacts:
        relative = artifact.path.relative_to(result.project_root)
        print(f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}")
    print()
    print("Result                    : SUCCESS")
    print("Synthesis                 : SEGA SOUND DRIVER + REAL GM BANKS")
    print("Channel 10                : DEDICATED GM DRUM BANK / GM NOTE MAP")
    print("Synthetic R26-R28 timbres : NOT USED")
    print("SAROO writes              : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
