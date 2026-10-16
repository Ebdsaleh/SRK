"""Print the read-only 128-program GM calibration inventory."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_gm_calibration_inventory import (
    audit_gm_calibration_inventory,
)


_FAMILY_NAMES = (
    "Piano", "Chromatic Percussion", "Organ", "Guitar",
    "Bass", "Strings", "Ensemble", "Brass",
    "Reed", "Pipe", "Synth Lead", "Synth Pad",
    "Synth Effects", "Ethnic", "Percussive", "Sound Effects",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-gm-calibration-inventory",
        description=(
            "Resolve the exact GeneralUser GS note-60/velocity-100 mapping and "
            "velocity attenuation model for all 128 GM programs. Read-only."
        ),
    )
    parser.add_argument("--soundfont", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit_gm_calibration_inventory(args.soundfont)
    except Exception as exc:
        print(
            f"srk-saturn-sbl-gm-calibration-inventory: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Saturn / 128-PROGRAM GM CALIBRATION INVENTORY")
    print("-------------------------------------------------")
    print(f"SoundFont              : {result.source_path}")
    print("Calibration note       : C4 / 60")
    print("Calibration velocity   : 100")
    print("Programs resolved      : 128 / 128")
    print("SAROO writes           : NONE")
    print("File modifications     : NONE")
    print("Hardware execution     : NONE")
    print()
    print("Velocity amounts (cB)  : " + ", ".join(
        f"{amount} x{count}" for amount, count in result.velocity_amount_counts
    ))
    print(
        "Other attenuation mods : "
        + (", ".join(map(str, result.rows_with_other_attenuation_modulators))
           if result.rows_with_other_attenuation_modulators else "NONE")
    )
    print()

    for family in range(16):
        print(f"Family {family:02d} {_FAMILY_NAMES[family]}")
        for row in result.rows[family * 8 : family * 8 + 8]:
            loop = "LOOP" if row.loop_enabled else "ONE-SHOT"
            print(
                f"  {row.program:03d}  {row.preset_name[:24]:24s}  "
                f"vel={row.velocity_amount_cb:4d}cB  {loop:8s}  "
                f"sample={row.sample_name[:24]}"
            )
        print()

    print("Next step              : fit every unique velocity amount, then author 16 family banks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
