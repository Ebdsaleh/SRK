"""CLI for read-only Space Spectre SoundFont level-model closure."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_level_model_audit import audit_gate3e_level_model


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
        prog="srk-saturn-sbl-level-model-audit",
        description=(
            "Read-only closure audit for GATE3E SoundFont static attenuation and explicit modulators. "
            "No candidate, media, or hardware action is performed."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="locked failed GATE3E project containing cd/SRKGM.BIN and cd/SRKDRUM.BIN",
    )
    parser.add_argument(
        "--soundfont",
        type=Path,
        help="optional local pinned GeneralUser GS .sf2; defaults to SRK's pinned cache",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_gate3e_level_model(args.project, args.soundfont)
    except Exception as exc:
        print(f"srk-saturn-sbl-level-model-audit: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK Space Spectre / SOUNDFONT LEVEL MODEL CLOSURE")
    print("------------------------------------------------")
    print(f"SoundFont             : {report.soundfont_path}")
    print(f"Historical reproduction: {'EXACT' if report.historical_reproduced else 'FAILED'}")
    print(f"PCM identity old->new : {'UNCHANGED' if report.sample_identity_preserved else 'CHANGED'}")
    print("Static SF2 attenuation: 40% compatibility projection (0.04 dB per centibel)")
    print("SCSP quantization      : nearest documented TL attenuation")
    print("SAROO writes           : NONE")
    print("File modifications     : NONE")
    print("Hardware execution     : NONE")
    print("GATE3F build           : BLOCKED")
    print("GATE3F deployment      : BLOCKED")
    print()

    print("Melodic level projection")
    for item in report.melodic_programs:
        name = _PROGRAM_NAMES.get(item.program, "unknown")
        print(
            f"  Program {item.program:3d} {name:18s}: rows={item.row_count:2d} "
            f"old median={item.old_median_rms_dbfs:+6.1f} dBFS -> "
            f"projected median={item.projected_median_rms_dbfs:+6.1f} dBFS "
            f"projected TL={item.projected_tl_min:3d}..{item.projected_tl_max:3d}"
        )
    print()

    print("Percussion level projection")
    for row in report.rows:
        if row.kind != "drum":
            continue
        name = _DRUM_NAMES.get(row.note, "unknown")
        print(
            f"  Note {row.note:3d} {name:18s}: "
            f"old TL={row.old_total_level:3d}/{row.old_attenuation_db:4.1f}dB "
            f"RMS={row.old_post_tl_rms_dbfs:+6.1f} -> "
            f"projected TL={row.projected_total_level:3d}/{row.projected_attenuation_db:4.1f}dB "
            f"RMS={row.projected_post_tl_rms_dbfs:+6.1f} dBFS"
        )
    print(f"  Drum spread          : {report.old_drum_spread_db:.1f} dB -> {report.projected_drum_spread_db:.1f} dB")
    print()

    print("Explicit SoundFont modulator inventory")
    print(f"  pmod active records  : {len(report.pmod_records)}")
    print(f"  imod active records  : {len(report.imod_records)}")
    print(f"  attenuation dest=48  : {len(report.attenuation_modulators)}")
    if report.destination_counts:
        print(
            "  destination counts   : "
            + ", ".join(f"{destination}={count}" for destination, count in report.destination_counts)
        )
    else:
        print("  destination counts   : NONE")
    for record in report.attenuation_modulators:
        print(
            f"    {record.table}[{record.index}] src=0x{record.source:04X} "
            f"amount={record.amount:+d} amountSrc=0x{record.amount_source:04X} "
            f"transform=0x{record.transform:04X}"
        )
    print()

    if report.attenuation_modulators:
        print("Closure status         : STATIC MAPPING EXPLAINS LARGE IMBALANCE, BUT EXPLICIT ATTENUATION MODULATORS REMAIN")
        print("Next step              : resolve relevant pmod/imod zone scope before changing the candidate builder")
    else:
        print("Closure status         : STATIC ATTENUATION PROJECTION HAS NO EXPLICIT DEST=48 MODULATOR CONFLICT")
        print("Next step              : lock corrected static level policy and rerun complete offline fidelity gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
