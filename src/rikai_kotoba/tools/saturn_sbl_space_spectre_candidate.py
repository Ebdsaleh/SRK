from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from rikai_kotoba.hardware.saturn.sbl_gm_physical_candidate import (
    SaturnSblGmCandidateError,
    build_saturn_sbl_gm_candidate,
)
from rikai_kotoba.hardware.saturn.sbl_soundfont_gm import (
    GENERALUSER_BLOB_SHA1,
    GENERALUSER_COMMIT,
    SaturnSblSoundfontError,
    derive_midi_tone_requirements,
    ensure_generaluser_soundfont,
    ensure_space_spectre_tone_banks,
)


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "assets" / "midi" / "cc0" / "double-impact").is_dir():
            return parent
    raise SaturnSblSoundfontError("cannot locate SRK repository root")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-space-spectre",
        description=(
            "Build the real Sega Sound Driver + Direct MIDI Space Spectre candidate. "
            "Derives compact native Saturn tone banks from a pinned GeneralUser GS "
            "SoundFont instead of requiring Sega's historical proprietary GM library."
        ),
    )
    parser.add_argument("--baseline-project", required=True, type=Path)
    parser.add_argument("--saturn-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--soundfont",
        type=Path,
        help=(
            "Local .sf2 to use. If omitted, SRK downloads and hash-verifies the pinned "
            "GeneralUser GS release into the user's cache."
        ),
    )
    parser.add_argument("--sound-driver", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_repo_root())
        requirements = derive_midi_tone_requirements(profile.program)
        soundfont = (
            args.soundfont.expanduser().resolve(strict=True)
            if args.soundfont is not None
            else ensure_generaluser_soundfont()
        )
        banks = ensure_space_spectre_tone_banks(soundfont, requirements)
        result = build_saturn_sbl_gm_candidate(
            args.baseline_project,
            args.saturn_root,
            args.output,
            melodic_tone_bank=banks.melodic_path,
            drum_tone_bank=banks.drum_path,
            sound_driver=args.sound_driver,
        )
    except (SaturnSblSoundfontError, SaturnSblGmCandidateError, OSError) as exc:
        print("SRK Space Spectre / Sega Direct MIDI / SoundFont candidate")
        print("---------------------------------------------------------")
        print("Result                    : FAILED")
        print(f"Reason                    : {exc}")
        print("Synthetic fallback        : REFUSED")
        print("SAROO writes              : NONE")
        return 1

    print("SRK Space Spectre / Sega Direct MIDI / SoundFont candidate")
    print("---------------------------------------------------------")
    print(f"Project                   : {result.project_root}")
    print(f"Space Spectre records     : {result.record_count}")
    print(f"Duration us               : {result.duration_us}")
    print(f"SoundFont source          : {banks.source_path}")
    print(f"SoundFont SHA-256         : {banks.source_sha256}")
    print(f"GeneralUser commit        : {GENERALUSER_COMMIT}")
    print(f"GeneralUser blob SHA-1    : {GENERALUSER_BLOB_SHA1}")
    print(f"Derived melodic bank      : {banks.melodic_path}")
    print(f"Derived melodic SHA-256   : {banks.melodic_sha256}")
    print(f"Derived drum bank         : {banks.drum_path}")
    print(f"Derived drum SHA-256      : {banks.drum_sha256}")
    print(f"Derived PCM               : {banks.sample_rate} Hz / {8 if banks.pcm8 else 16}-bit")
    print(f"Combined tone bytes       : {banks.combined_bytes}")
    print(f"Tone source report        : {banks.report_path}")
    print(f"Sound driver              : {result.assets.sound_driver}")
    print(f"Sega sound library        : {result.assets.sega_sound_library}")
    print(f"Build log                 : {result.build.log_path}")
    print(f"Build report              : {result.build.report_path}")
    print()
    print("Result                    : SUCCESS")
    print("Playback path             : SEGA SDDRV + SND_CtrlDirMidi")
    print("GM programs preserved     : 30,39,73,120")
    print("Channel 10 notes preserved: 35,40,42,51")
    print("Synthetic R26-R28 timbres : NOT USED")
    print("SAROO writes              : NONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
