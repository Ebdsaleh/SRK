"""CLI for read-only GATE3E PCM/TL balance analysis."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_pcm_balance_audit import audit_gate3e_pcm_balance


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
        prog="srk-saturn-sbl-pcm-balance-audit",
        description=(
            "Read-only artifact-level audit of failed GATE3E PCM amplitude and SCSP TL attenuation. "
            "No media, build or hardware action is performed."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="locked failed GATE3E project containing cd/SRKGM.BIN and cd/SRKDRUM.BIN",
    )
    return parser


def _fmt_db(value: float) -> str:
    return "-inf" if math.isinf(value) and value < 0 else f"{value:+.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_gate3e_pcm_balance(args.project)
    except Exception as exc:
        print(f"srk-saturn-sbl-pcm-balance-audit: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK Space Spectre / GATE3E PCM + TL BALANCE AUDIT")
    print("------------------------------------------------")
    print(f"Melodic SHA-256      : {report.melodic_sha256}")
    print(f"Drum SHA-256         : {report.drum_sha256}")
    print("TL model             : Sega SCSP documented bit attenuation")
    print("Level scope          : PCM + TL only; velocity/EG not yet applied")
    print("SAROO writes         : NONE")
    print("File modifications   : NONE")
    print("Hardware execution   : NONE")
    print("GATE3F deployment    : BLOCKED")
    print()

    print("Melodic program balance")
    for item in report.melodic_programs:
        name = _PROGRAM_NAMES.get(item.program, "unknown")
        print(
            f"  Program {item.program:3d} {name:18s}: rows={item.row_count:2d} "
            f"TL={item.tl_min:3d}..{item.tl_max:3d} "
            f"post-TL RMS min/med/max={_fmt_db(item.post_tl_rms_min_dbfs)}/"
            f"{_fmt_db(item.post_tl_rms_median_dbfs)}/{_fmt_db(item.post_tl_rms_max_dbfs)} dBFS "
            f"ToneEditor>127={item.tone_editor_range_exceeded}"
        )
    print()

    print("Percussion rows")
    for row in report.drum_rows:
        name = _DRUM_NAMES.get(row.note, "unknown")
        print(
            f"  Note {row.note:3d} {name:18s}: vel={row.representative_velocity:3d} "
            f"TL={row.total_level:3d} ({row.tl_attenuation_db:4.1f} dB) "
            f"PCM RMS={_fmt_db(row.pcm_rms_dbfs)} dBFS -> "
            f"post-TL RMS={_fmt_db(row.post_tl_rms_dbfs)} dBFS "
            f"peak={_fmt_db(row.post_tl_peak_dbfs)} dBFS"
        )
    print(f"  Static drum spread : {report.drum_static_spread_db:.1f} dB before velocity/EG")
    print()

    violations = tuple(row for row in report.melodic_rows if row.tone_editor_range_exceeded)
    print("Tone Editor authored-range observation")
    print("  Sega Tone Editor UI documents layer Total Level as 0..127.")
    print("  SCSP hardware TL is still an 8-bit register, so >127 is not called hardware-invalid here.")
    print(f"  Used melodic rows >127: {len(violations)} / {len(report.melodic_rows)}")
    for row in violations:
        print(
            f"    program {row.program:3d} note {row.note:3d}: TL={row.total_level:3d} "
            f"({row.tl_attenuation_db:4.1f} dB), raw RMS={_fmt_db(row.pcm_rms_dbfs)}, "
            f"post-TL RMS={_fmt_db(row.post_tl_rms_dbfs)} dBFS"
        )
    print()
    print("Interpretation rule  : large post-TL gaps are real artifact-level balance evidence;")
    print("                       do not alter TL until PCM amplitude is included as above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
