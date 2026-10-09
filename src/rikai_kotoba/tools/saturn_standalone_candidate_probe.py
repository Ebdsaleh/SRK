"""Developer-facing read-only ranking of local Saturn standalone projects."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.standalone_candidates import (
    inspect_saturn_standalone_candidates,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-standalone-candidates",
        description=(
            "Read-only ranking of concrete local Saturn project directories. "
            "Candidates are evidence for review, not a build-readiness claim."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="Saturn development root to inspect without modifying it",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Maximum ranked project candidates to report (default: 12)",
    )
    return parser


def _print_paths(label: str, paths: tuple[object, ...], *, limit: int = 20) -> None:
    print(f"{label}: {len(paths)}")
    for path in paths[:limit]:
        print(f"  {path}")
    if len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = inspect_saturn_standalone_candidates(
            args.saturn_root,
            candidate_limit=args.limit,
        )
    except Exception as exc:
        print(
            f"srk-saturn-standalone-candidates: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK standalone Saturn candidate probe")
    print("-" * 44)
    print(f"Saturn root   : {report.root}")
    print("Access policy : READ-ONLY discovery; no files or PATH are modified")
    print()

    print("Library / startup evidence")
    print("--------------------------")
    _print_paths("Library artifacts", report.libraries)
    _print_paths("Support objects", report.support_objects)
    print()

    print("Ranked standalone project candidates")
    print("------------------------------------")
    if not report.candidates:
        print("[none]")
    for index, candidate in enumerate(report.candidates, start=1):
        print(f"[{index}] score {candidate.score}: {candidate.directory}")
        print("    evidence : " + ", ".join(candidate.evidence))
        if candidate.makefiles:
            print("    makefile : " + str(candidate.makefiles[0]))
            if len(candidate.makefiles) > 1:
                print(f"    makefiles: {len(candidate.makefiles)} total")
        else:
            print("    makefile : [none in candidate directory]")
        print(f"    IP.BIN   : {candidate.ip_bin or '[none in candidate directory]'}")
        print(f"    sources  : {len(candidate.source_files)}")
        print(f"    linker   : {len(candidate.linker_files)}")
        print(f"    startup  : {len(candidate.startup_files)}")
        for source in candidate.source_files[:5]:
            print(f"      src    : {source.name}")
        if len(candidate.source_files) > 5:
            print(f"      ... {len(candidate.source_files) - 5} more source files")
        print()

    print("Interpretation")
    print("--------------")
    print(
        "Higher scores mean more local boot/build evidence is colocated with the "
        "project. A candidate must still be inspected before SRK copies or builds it."
    )
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
