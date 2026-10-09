"""Prepare an isolated SRK standalone Sega Saturn diagnostics project."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.standalone_project import (
    prepare_saturn_standalone_project,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-standalone-prepare",
        description=(
            "Generate a separate SRK Saturn Diagnostics R1 project from the "
            "reviewed local SH-ELF environment, one vdp1ex font asset, and one "
            "local IP.BIN. Source SDK/example trees remain read only."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root used for read-only SH-ELF/mkisofs discovery",
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Reviewed vdp1ex directory containing vga_font.h",
    )
    parser.add_argument(
        "--ip-bin",
        required=True,
        help="Reviewed local Saturn IP.BIN to copy and patch in the generated tree",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="New output directory; must not already exist",
    )
    parser.add_argument(
        "--release-date",
        help="Optional Saturn System ID date as YYYYMMDD (defaults to current UTC date)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = prepare_saturn_standalone_project(
            args.saturn_root,
            args.template,
            args.ip_bin,
            args.output,
            release_date=args.release_date,
        )
    except Exception as exc:
        print(
            f"srk-saturn-standalone-prepare: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK standalone Saturn diagnostics project prepared")
    print("-" * 50)
    print(f"Output tree : {result.output_root}")
    print(f"Source      : {result.source_root}")
    print(f"IP.BIN      : {result.ip_bin}")
    print(f"Manifest    : {result.manifest}")
    print(f"Build wrapper: {result.build_script}")
    print()
    print("Resolved local tools")
    print(f"  sh-elf-gcc : {result.gcc}")
    print(f"  sh-elf-as  : {result.assembler}")
    print(f"  ISO builder: {result.iso_builder}")
    print()
    print("Safety")
    print("  Installed Saturn SDK/example trees were read only and were not modified.")
    print("  The source IP.BIN was not modified; the generated tree contains a patched copy.")
    print("  No compiler, linker, ISO builder, game image, or SD-card write was executed.")
    print()
    print("Preferred next step after review (from the SRK virtual environment):")
    print("  python -m rikai_kotoba.tools.saturn_standalone_build ^")
    print(f'    --project "{result.output_root}"')
    print("  build.bat is a convenience wrapper around the same Python-native command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
