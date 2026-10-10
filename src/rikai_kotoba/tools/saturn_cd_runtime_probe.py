"""Read-only local evidence probe for Stage 6B Saturn CD/filesystem work."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.cd_runtime_probe import (
    inspect_saturn_cd_runtime_evidence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-cd-runtime-probe",
        description=(
            "Read-only discovery of local Sega Saturn GFS/CDC libraries, headers, "
            "and GFS_* source/example/documentation evidence. No local Saturn file "
            "is modified or executed."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root to inspect read-only",
    )
    parser.add_argument(
        "--match-limit",
        type=int,
        default=120,
        help="Maximum GFS text matches to print (default: 120)",
    )
    return parser


def _print_paths(label: str, paths: tuple[object, ...], *, limit: int = 60) -> None:
    print(f"{label}: {len(paths)}")
    for path in paths[:limit]:
        print(f"  {path}")
    if len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.match_limit <= 0:
        parser.error("--match-limit must be positive")

    try:
        report = inspect_saturn_cd_runtime_evidence(args.saturn_root)
    except Exception as exc:
        print(
            f"srk-saturn-cd-runtime-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Saturn CD/filesystem runtime evidence probe")
    print("-" * 52)
    print(f"Saturn root      : {report.root}")
    print("Access policy    : READ-ONLY; no files are created, copied, modified, or executed")
    print(f"Text files read  : {report.scanned_text_files}")
    print(f"Oversize skipped : {report.skipped_oversize_files}")
    print()

    _print_paths("GFS/CDC library artifacts", report.libraries)
    print()
    _print_paths("Likely CD/GFS/CDC headers", report.likely_headers)
    print()

    print("GFS textual evidence")
    print("--------------------")
    if not report.text_matches:
        print("[none]")
    for match in report.text_matches[: args.match_limit]:
        symbols = ", ".join(match.symbols) if match.symbols else "text signal"
        print(f"{match.path}:{match.line_number}")
        print(f"  symbols: {symbols}")
        print(f"  {match.line}")
    if len(report.text_matches) > args.match_limit:
        print(f"... {len(report.text_matches) - args.match_limit} more matches not printed")

    print()
    print("Interpretation")
    print("--------------")
    print("This report is evidence for Stage 6B design, not permission to copy Sega code.")
    print("Prefer supplied Sega/SBL documentation and known-good local examples.")
    print("Do not infer low-level CD block commands from filenames alone.")
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
