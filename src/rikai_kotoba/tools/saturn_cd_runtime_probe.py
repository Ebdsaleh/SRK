"""Read-only local evidence probe for Stage 6B Saturn CD/filesystem work."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.cd_runtime_probe import (
    SaturnCdRuntimeTextMatch,
    inspect_saturn_cd_runtime_evidence,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-cd-runtime-probe",
        description=(
            "Read-only discovery of local Sega Saturn GFS/CDC libraries, headers, "
            "API declarations, build/link evidence, and GFS_* source/example/"
            "documentation evidence. No local Saturn file is modified or executed."
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
        help="Maximum general GFS text matches to print (default: 120)",
    )
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help=(
            "Print preferred installed artifact fingerprints plus prioritized API "
            "declaration and build/link evidence, omitting the broad text listing"
        ),
    )
    return parser


def _print_paths(label: str, paths: tuple[object, ...], *, limit: int = 60) -> None:
    print(f"{label}: {len(paths)}")
    for path in paths[:limit]:
        print(f"  {path}")
    if len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def _print_matches(
    title: str,
    matches: tuple[SaturnCdRuntimeTextMatch, ...],
    *,
    limit: int | None = None,
) -> None:
    print(title)
    print("-" * len(title))
    selected = matches if limit is None else matches[:limit]
    if not selected:
        print("[none]")
    for match in selected:
        symbols = ", ".join(match.symbols) if match.symbols else "text signal"
        print(f"{match.path}:{match.line_number}")
        print(f"  symbols: {symbols}")
        print(f"  {match.line}")
    if limit is not None and len(matches) > limit:
        print(f"... {len(matches) - limit} more matches not printed")


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

    print("Preferred installed SBL artifacts")
    print("---------------------------------")
    if not report.preferred_artifacts:
        print("[none]")
    for artifact in report.preferred_artifacts:
        print(f"{artifact.role}: {artifact.path}")
        print(f"  size    : {artifact.size}")
        print(f"  SHA-256 : {artifact.sha256}")
    print()

    _print_matches("Prioritized GFS API contract lines", report.api_contract_matches)
    print()
    _print_matches("Local GFS/CDC build-link evidence", report.link_matches)

    if not args.contract_only:
        print()
        _print_paths("GFS/CDC library artifacts", report.libraries)
        print()
        _print_paths("Likely CD/GFS/CDC headers", report.likely_headers)
        print()
        _print_matches(
            "GFS textual evidence",
            report.text_matches,
            limit=args.match_limit,
        )

    print()
    print("Interpretation")
    print("--------------")
    print("This report is evidence for Stage 6B design, not permission to copy Sega code.")
    print("Prefer supplied Sega/SBL documentation and known-good local examples.")
    print("Artifact hashes identify local dependencies without copying them into SRK.")
    print("Do not infer low-level CD block commands from filenames alone.")
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
