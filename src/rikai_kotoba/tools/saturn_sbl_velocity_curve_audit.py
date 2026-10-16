"""Read-only Space Spectre Sega velocity-table closure audit."""

from __future__ import annotations

import argparse
from collections import Counter
from math import log10
from pathlib import Path
from statistics import median

from rikai_kotoba.hardware.saturn.sbl_level_model_audit import audit_gate3e_level_model
from rikai_kotoba.hardware.saturn.sbl_modulator_scope_audit import (
    audit_space_spectre_modulator_scope,
)
from rikai_kotoba.hardware.saturn.sbl_velocity_curve import (
    SPACE_SPECTRE_VELOCITY_AMOUNTS_CB,
    audit_velocity_table,
    sega_velocity_level,
    soundfont_velocity_attenuation_db,
    table_for_velocity_amount,
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Sega-native velocity curves for the exact GATE3E SoundFont zones."
    )
    parser.add_argument("--project", required=True, help="Physically failed GATE3E project directory")
    parser.add_argument("--soundfont", help="Optional pinned GeneralUser GS path")
    return parser


def _db_from_sega_level(level: int) -> float:
    return -20.0 * log10(max(1, int(level)) / 127.0)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = Path(args.project).expanduser().resolve(strict=True)
    soundfont = None if not args.soundfont else Path(args.soundfont).expanduser().resolve(strict=True)

    scope = audit_space_spectre_modulator_scope(project, soundfont)
    level = audit_gate3e_level_model(project, soundfont)
    if not scope.historical_reproduced or not level.historical_reproduced:
        raise SystemExit("historical GATE3E reproduction is not exact")
    if scope.rows_with_other_attenuation_modulators:
        raise SystemExit("used zones still contain non-velocity destination-48 modulators")
    if scope.velocity_amounts != SPACE_SPECTRE_VELOCITY_AMOUNTS_CB:
        raise SystemExit(
            "used velocity amounts changed: "
            + ", ".join(str(value) for value in scope.velocity_amounts)
        )

    static_rows = {(row.kind, row.program, row.note): row for row in level.rows}
    if set(static_rows) != {row.key for row in scope.rows}:
        raise SystemExit("static-level and modulator-scope rows do not match")

    print("SRK Space Spectre / SEGA VELOCITY CURVE CLOSURE")
    print("------------------------------------------------")
    print(f"SoundFont               : {scope.soundfont_path}")
    print("Historical reproduction : EXACT")
    print("Used dest-48 extras     : NONE")
    print("Required SF2 amounts    : " + ", ".join(f"+{value}cB" for value in scope.velocity_amounts))
    print("Sega table source       : supplied NON.ASM / SCSP.LIB 10-byte K/V/L format")
    print("SAROO writes            : NONE")
    print("File modifications      : NONE")
    print("Tone-bank generation    : NONE")
    print("Hardware execution      : NONE")
    print("GATE3F build            : BLOCKED")
    print("GATE3F deployment       : BLOCKED")
    print()

    print("Locked Sega-native velocity curves")
    for amount in scope.velocity_amounts:
        audit = audit_velocity_table(amount)
        print(
            f"  +{amount:3d}cB table: {audit.table.hex(' ').upper()}  "
            f"linear max={audit.max_linear_error:.2f} RMS={audit.rms_linear_error:.2f}  "
            f"checkpoint max={audit.max_checkpoint_error_db:.3f}dB mean={audit.mean_checkpoint_error_db:.3f}dB"
        )
        for point in audit.checkpoints:
            print(
                f"      v={point.velocity:3d}: SF2={point.target_level:7.3f} "
                f"Sega={point.sega_level:3d} error={point.error_db:+.3f}dB"
            )
    print()

    melodic_amounts: dict[int, set[int]] = {}
    drum_amounts: dict[int, int] = {}
    for row in scope.rows:
        if row.kind == "melodic":
            melodic_amounts.setdefault(row.program, set()).add(row.velocity_attenuation_amount_cb)
        else:
            drum_amounts[row.note] = row.velocity_attenuation_amount_cb

    melodic_catalog = tuple(sorted({value for values in melodic_amounts.values() for value in values}))
    drum_catalog = tuple(sorted(set(drum_amounts.values())))
    print("Per-bank velocity-table plan")
    print(
        "  Melodic tables: "
        + ", ".join(f"index {index}=+{amount}cB" for index, amount in enumerate(melodic_catalog))
    )
    for program in sorted(melodic_amounts):
        values = melodic_amounts[program]
        if len(values) != 1:
            raise SystemExit(f"program {program} unexpectedly uses multiple velocity amounts")
        amount = next(iter(values))
        print(
            f"    Program {program:3d} {_PROGRAM_NAMES.get(program, 'Unknown'):<18}: "
            f"+{amount}cB -> table {melodic_catalog.index(amount)}"
        )
    print(
        "  Drum tables   : "
        + ", ".join(f"index {index}=+{amount}cB" for index, amount in enumerate(drum_catalog))
    )
    for note in sorted(drum_amounts):
        amount = drum_amounts[note]
        print(
            f"    Note {note:3d} {_DRUM_NAMES.get(note, 'Unknown'):<18}: "
            f"+{amount}cB -> table {drum_catalog.index(amount)}"
        )
    print()

    combined_rows = []
    print("Representative used-row level projection")
    for row in scope.rows:
        static = static_rows[row.key]
        sega_level = sega_velocity_level(
            table_for_velocity_amount(row.velocity_attenuation_amount_cb), row.velocity
        )
        sf2_db = soundfont_velocity_attenuation_db(row.velocity_attenuation_amount_cb, row.velocity)
        sega_db = _db_from_sega_level(sega_level)
        combined = static.projected_post_tl_rms_dbfs - sega_db
        combined_rows.append((row.kind, row.program, row.note, combined, sega_db - sf2_db))

    for program in sorted(melodic_amounts):
        selected = [item for item in combined_rows if item[0] == "melodic" and item[1] == program]
        values = [item[3] for item in selected]
        errors = [abs(item[4]) for item in selected]
        print(
            f"  Program {program:3d} {_PROGRAM_NAMES.get(program, 'Unknown'):<18}: "
            f"rows={len(values):2d} combined RMS min/med/max="
            f"{min(values):6.1f}/{median(values):6.1f}/{max(values):6.1f} dBFS  "
            f"velocity model max error={max(errors):.3f}dB"
        )
    for note in sorted(drum_amounts):
        item = next(
            value for value in combined_rows if value[0] == "drum" and value[2] == note
        )
        source_row = next(row for row in scope.rows if row.kind == "drum" and row.note == note)
        print(
            f"  Note {note:3d} {_DRUM_NAMES.get(note, 'Unknown'):<18}: "
            f"velocity={source_row.velocity:3d} combined RMS={item[3]:6.1f} dBFS  "
            f"velocity model error={item[4]:+.3f}dB"
        )
    print()

    counts = Counter(row.velocity_attenuation_amount_cb for row in scope.rows)
    print(
        "Assignment counts        : "
        + ", ".join(f"+{amount}cB x{counts[amount]}" for amount in sorted(counts))
    )
    print("Closure status           : SEGA VELOCITY TABLE MODEL READY FOR OFFLINE BANK AUTHORING")
    print("Next step                : author multi-table TON banks in memory and re-run fidelity gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
