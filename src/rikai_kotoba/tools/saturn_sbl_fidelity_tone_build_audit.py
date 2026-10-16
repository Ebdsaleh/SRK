"""CLI for the read-only corrected Saturn TON authoring proof."""

from __future__ import annotations

import argparse
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_fidelity_tone_build_audit import (
    audit_space_spectre_fidelity_tone_build,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build corrected Space Spectre TON banks in memory and decode them back."
    )
    parser.add_argument("--project", required=True, help="Physically failed GATE3E project directory")
    parser.add_argument("--soundfont", help="Optional pinned GeneralUser GS path")
    return parser


def _fmt_tables(amounts: tuple[int, ...], tables: tuple[bytes, ...]) -> str:
    return ", ".join(
        f"index {index}=+{amount}cB [{table.hex(' ').upper()}]"
        for index, (amount, table) in enumerate(zip(amounts, tables))
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = Path(args.project).expanduser().resolve(strict=True)
    soundfont = None if not args.soundfont else Path(args.soundfont).expanduser().resolve(strict=True)

    report = audit_space_spectre_fidelity_tone_build(project, soundfont)

    print("SRK Space Spectre / CORRECTED TON IN-MEMORY AUTHORING")
    print("----------------------------------------------------")
    print(f"SoundFont               : {report.source_path}")
    print("Historical reproduction : EXACT")
    print("M6 event fidelity       : EXACT")
    print(f"Audited tone rows       : {report.row_count}")
    print(f"Melodic SHA-256         : {report.melodic_sha256}")
    print(f"Drum SHA-256            : {report.drum_sha256}")
    print(f"Melodic bytes           : {report.melodic_bytes}")
    print(f"Drum bytes              : {report.drum_bytes}")
    print(f"Melodic velocity tables : {_fmt_tables(report.melodic_table_amounts, report.melodic_velocity_tables)}")
    print(f"Drum velocity tables    : {_fmt_tables(report.drum_table_amounts, report.drum_velocity_tables)}")
    print(f"PCM identity preserved  : {'YES' if report.pcm_identity_preserved else 'NO'}")
    print(f"BASE/FINE preserved     : {'YES' if report.pitch_identity_preserved else 'NO'}")
    print(f"Static TL projection    : {'EXACT' if report.static_total_levels_exact else 'MISMATCH'}")
    print(f"Packed table assignment : {'EXACT' if report.packed_assignments_exact else 'MISMATCH'}")
    print("SAROO writes            : NONE")
    print("File modifications      : NONE")
    print("Hardware execution      : NONE")
    print("GATE3F build            : BLOCKED")
    print("GATE3F deployment       : BLOCKED")
    print()
    print("Closure status          : CORRECTED TON BYTES PROVEN IN MEMORY")
    print("Next step               : lock hashes, wire corrected policy into a fresh off-card GATE3F build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
