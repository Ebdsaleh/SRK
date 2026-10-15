"""CLI for read-only GATE3E vs current Saturn tone-policy comparison."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_tone_revision_audit import (
    audit_gate3e_to_current_tone_policy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-tone-revision-audit",
        description=(
            "Read-only reproduction of the failed GATE3E tone banks followed by "
            "an in-memory comparison against the current corrected SoundFont policy."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        type=Path,
        help="failed GATE3E candidate containing cd/SRKGM.BIN and cd/SRKDRUM.BIN",
    )
    parser.add_argument(
        "--soundfont",
        type=Path,
        help="optional local pinned GeneralUser-GS.sf2; defaults to SRK's existing cache",
    )
    return parser


def _row_label(row) -> str:
    if row.kind == "drum":
        return f"drum note {row.note}"
    return f"program {row.program} note {row.note}"


def _compact(row) -> str:
    return (
        f"preset={row.preset_bank}:{row.preset_name!r} sample={row.sample_id}:{row.sample_name!r} "
        f"src={row.source_rate}Hz root={row.source_root} corr={row.pitch_correction:+d} "
        f"zone_tune={row.zone_coarse:+d}st/{row.zone_fine:+d}c att={row.attenuation_cb}cb "
        f"BASE={row.base_note} FINE={row.fine_tune:+d} TL={row.total_level} "
        f"ADSR={row.attack_rate}/{row.decay_rate}/{row.decay_level}/{row.release_rate} "
        f"loop={int(row.loop_enabled)}:{row.loop_start}-{row.loop_end} pcm={row.pcm_sha256[:16]}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_gate3e_to_current_tone_policy(
            args.project,
            args.soundfont,
            repository_root=Path.cwd(),
        )
    except Exception as exc:
        print(
            f"srk-saturn-sbl-tone-revision-audit: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    old = report.historical
    new = report.corrected
    print("SRK Space Spectre / TONE POLICY REVISION AUDIT")
    print("------------------------------------------------")
    print(f"SoundFont           : {report.source_path}")
    print(f"SoundFont blob SHA1 : {report.source_blob_sha1}")
    print("SAROO writes        : NONE")
    print("File modifications  : NONE")
    print("Hardware execution  : NONE")
    print("GATE3F deployment   : BLOCKED")
    print()

    print("Historical GATE3E reproduction")
    print(f"  Actual melodic SHA : {report.actual_melodic_sha256}")
    print(f"  Model melodic SHA  : {old.melodic_sha256}")
    print(f"  Actual drum SHA    : {report.actual_drum_sha256}")
    print(f"  Model drum SHA     : {old.drum_sha256}")
    print(f"  PCM representation : {old.sample_rate} Hz / {8 if old.pcm8 else 16}-bit")
    print(f"  Result             : {'EXACT' if report.historical_reproduced else 'MISMATCH'}")
    print()

    print("Current corrected policy")
    print(f"  Melodic SHA        : {new.melodic_sha256}")
    print(f"  Drum SHA           : {new.drum_sha256}")
    print(f"  Melodic bytes      : {new.melodic_bytes}")
    print(f"  Drum bytes         : {new.drum_bytes}")
    print(f"  PCM representation : {new.sample_rate} Hz / {8 if new.pcm8 else 16}-bit")
    print(f"  Changed tone rows  : {len(report.changed_rows)} / {len(old.rows)}")
    print()

    field_counts = Counter(
        field
        for _before, _after, fields in report.changed_rows
        for field in fields
    )
    print("Changed-field counts")
    if field_counts:
        for field, count in sorted(field_counts.items()):
            print(f"  {field:18s}: {count}")
    else:
        print("  NONE")
    print()

    print("Changed Space Spectre tone rows")
    if not report.changed_rows:
        print("  NONE")
    for before, after, fields in report.changed_rows:
        print(f"  {_row_label(before)} fields={','.join(fields)}")
        print(f"    OLD: {_compact(before)}")
        print(f"    NEW: {_compact(after)}")
    print()

    if not report.historical_reproduced:
        print("Comparison status   : BLOCKED - historical model did not reproduce GATE3E")
        return 1
    if not report.changed_rows:
        print("Comparison status   : EXACT OLD/NEW SEMANTICS - hierarchy fix does not explain failure")
    else:
        print("Comparison status   : TRUSTED OLD->NEW DIFFERENCES FOUND")
        print("Next step           : interpret differences offline before any GATE3F build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
