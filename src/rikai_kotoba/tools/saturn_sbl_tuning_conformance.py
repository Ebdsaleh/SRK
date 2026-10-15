"""CLI for read-only Sega Saturn SCSPBIN fine-tune conformance auditing."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from rikai_kotoba.hardware.saturn.sbl_soundfont_channel10 import (
    SEGA_FINE_TUNE_MAX,
    SEGA_FINE_TUNE_MIN,
)
from rikai_kotoba.hardware.saturn.sbl_tuning_conformance import (
    SaturnFineTuneBankReport,
    audit_space_spectre_fine_tuning,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-sbl-tuning-conformance",
        description=(
            "Read-only audit of generated SCSPBIN layer Fine Tune values against "
            "Sega Tone Editor's documented -63..+63 range."
        ),
    )
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    return parser


def _render_bank(label: str, report: SaturnFineTuneBankReport) -> None:
    print(label)
    print(f"  Path             : {report.bank.path}")
    print(f"  SHA-256          : {report.bank.sha256}")
    print(f"  Voices           : {report.bank.voice_count}")
    print(f"  Layers           : {report.layer_count}")
    print(f"  Fine range       : {report.minimum:+d} .. {report.maximum:+d}")
    print(f"  Violations       : {len(report.violations)}")
    print(f"  Status           : {'CONFORMING' if report.conforming else 'NONCONFORMING'}")
    for item in report.violations:
        print(
            "    "
            f"voice={item.voice:3d} layer={item.layer:3d} "
            f"notes={item.start_note:3d}..{item.end_note:3d} "
            f"base={item.base_note:3d} fine={item.fine_tune:+d}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_space_spectre_fine_tuning(
            args.project,
            reference_tone_bank=args.reference,
        )
    except Exception as exc:
        print(
            f"srk-saturn-sbl-tuning-conformance: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Saturn / SCSPBIN FINE-TUNE CONFORMANCE")
    print("-------------------------------------------")
    print(f"Sega documented range : {SEGA_FINE_TUNE_MIN:+d} .. {SEGA_FINE_TUNE_MAX:+d}")
    print("SAROO writes           : NONE")
    print("File modifications     : NONE")
    print("Hardware execution     : NONE")
    print("GATE3F deployment      : BLOCKED")
    print()
    _render_bank("Generated melodic bank", report.melodic)
    print()
    _render_bank("Generated drum bank", report.drums)
    if report.reference is not None:
        print()
        _render_bank("Sega reference bank", report.reference)
    print()
    print(
        "Generated tuning status : "
        + ("CONFORMING" if report.conforming else "NONCONFORMING")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
