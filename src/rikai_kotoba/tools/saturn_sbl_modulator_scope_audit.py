"""CLI for exact Space Spectre SoundFont attenuation-modulator scope."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_modulator_scope_audit import (
    SaturnModulatorScopeRow,
    audit_space_spectre_modulator_scope,
    decode_modulator_source,
    default_velocity_identity,
)


_PROGRAM_NAMES = {
    30: "Distortion Guitar",
    39: "Synth Bass 2",
    73: "Flute",
    120: "Fret Noise",
}
_DRUM_NAMES = {
    35: "Acoustic Bass Drum",
    40: "Electric Snare",
    42: "Closed Hi-Hat",
    51: "Ride Cymbal 1",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-modulator-scope-audit",
        description=(
            "Resolve pmod/imod attenuation modulators only for the exact SoundFont zones "
            "used by Space Spectre. Read-only: no bank build, media or hardware action."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="locked physically failed GATE3E project",
    )
    parser.add_argument(
        "--soundfont",
        type=Path,
        default=None,
        help="optional pinned GeneralUser SF2 path; default is SRK's pinned cache",
    )
    return parser


def _mod_text(row: SaturnModulatorScopeRow) -> str:
    others = row.non_velocity_attenuation_modulators
    if not others:
        return "none"
    return "; ".join(
        f"src=0x{mod.identity.source:04X}({decode_modulator_source(mod.identity.source)}) "
        f"amount={mod.amount:+d}cB via={'+'.join(mod.provenance)}"
        for mod in others
    )


def _program_summary(rows: Sequence[SaturnModulatorScopeRow], program: int) -> None:
    selected = tuple(row for row in rows if row.kind == "melodic" and row.program == program)
    amounts = Counter(row.velocity_attenuation_amount_cb for row in selected)
    instruments = sorted({row.instrument_name for row in selected})
    name = _PROGRAM_NAMES.get(program, "unknown")
    amount_text = ", ".join(f"{amount:+d}cB x{count}" for amount, count in sorted(amounts.items()))
    other_rows = sum(bool(row.non_velocity_attenuation_modulators) for row in selected)
    print(
        f"  Program {program:3d} {name:18s}: rows={len(selected):2d} "
        f"velocity amount(s)={amount_text} other-dest48-rows={other_rows}"
    )
    print(f"    instrument(s)       : {', '.join(instruments)}")
    if len(amounts) > 1 or other_rows:
        by_signature: dict[tuple[int, str], list[int]] = defaultdict(list)
        for row in selected:
            by_signature[(row.velocity_attenuation_amount_cb, _mod_text(row))].append(row.note)
        for (amount, other), notes in sorted(by_signature.items()):
            print(
                f"    notes {min(notes):3d}..{max(notes):3d} ({len(notes):2d}) "
                f"velocity={amount:+d}cB other={other}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_space_spectre_modulator_scope(
            args.project,
            args.soundfont,
        )
    except Exception as exc:
        print(f"srk-saturn-sbl-modulator-scope-audit: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK Space Spectre / USED-ZONE SOUNDFONT MODULATOR SCOPE")
    print("--------------------------------------------------------")
    print(f"SoundFont              : {report.soundfont_path}")
    print("Historical reproduction: EXACT")
    print(f"Resolved semantic rows : {len(report.rows)}")
    identity = default_velocity_identity()
    print(
        "Velocity identity       : "
        f"src=0x{identity.source:04X} ({decode_modulator_source(identity.source)}) "
        "-> initialAttenuation"
    )
    print("Implicit default amount : +960 cB at instrument level")
    print("Hierarchy rule          : instrument explicit replaces default; preset adds")
    print("SAROO writes            : NONE")
    print("File modifications      : NONE")
    print("Tone-bank generation    : NONE")
    print("Hardware execution      : NONE")
    print("GATE3F build            : BLOCKED")
    print("GATE3F deployment       : BLOCKED")
    print()

    print("Melodic used-zone attenuation modulators")
    for program in (30, 39, 73, 120):
        _program_summary(report.rows, program)
    print()

    print("Percussion used-zone attenuation modulators")
    for row in sorted(
        (row for row in report.rows if row.kind == "drum"),
        key=lambda value: value.note,
    ):
        name = _DRUM_NAMES.get(row.note, "unknown")
        print(
            f"  Note {row.note:3d} {name:18s}: velocity={row.velocity:3d} "
            f"effective velocity amount={row.velocity_attenuation_amount_cb:+d}cB"
        )
        print(
            f"    preset={row.preset_bank}:{row.program} {row.preset_name!r} "
            f"bags global/local={row.preset_global_bag}/{row.preset_local_bag}"
        )
        print(
            f"    instrument={row.instrument_index} {row.instrument_name!r} "
            f"bags global/local={row.instrument_global_bag}/{row.instrument_local_bag} "
            f"sample={row.sample_id} {row.sample_name!r}"
        )
        print(f"    other destination-48 : {_mod_text(row)}")
    print()

    amount_counts = Counter(row.velocity_attenuation_amount_cb for row in report.rows)
    print("Whole-song used-zone summary")
    print(
        "  Effective velocity amounts: "
        + ", ".join(f"{amount:+d}cB x{count}" for amount, count in sorted(amount_counts.items()))
    )
    other_rows = report.rows_with_other_attenuation_modulators
    print(f"  Rows with non-velocity destination-48 modulators: {len(other_rows)} / {len(report.rows)}")
    for row in other_rows:
        print(f"    {row.kind} program={row.program} note={row.note}: {_mod_text(row)}")
    print()

    if other_rows:
        print("Closure status          : ADDITIONAL DESTINATION-48 MODULATORS REQUIRE MODELING")
        print("Next step               : model these used-zone sources before Saturn velocity-table synthesis")
    elif len(amount_counts) > 1:
        print("Closure status          : USED ATTENUATION MODULATORS RESOLVED; MULTIPLE VELOCITY CURVES REQUIRED")
        print("Next step               : synthesize per-amount Saturn velocity tables and assign layers explicitly")
    else:
        print("Closure status          : USED ATTENUATION MODULATORS RESOLVED; ONE VELOCITY CURVE SUFFICES")
        print("Next step               : synthesize and validate the single required Saturn velocity table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
