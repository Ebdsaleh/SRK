"""Developer-facing read-only inspection of one Saturn standalone template."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.standalone_template import (
    inspect_saturn_standalone_template,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-standalone-template",
        description=(
            "Read-only inspection of one concrete Saturn standalone project. "
            "Reports hashes, IP.BIN metadata, and bounded build/source excerpts."
        ),
    )
    parser.add_argument(
        "--candidate",
        required=True,
        help="Exact standalone project directory to inspect without modifying it",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=220,
        help="Maximum text lines printed per reviewed file (default: 220)",
    )
    return parser


def _print_text_file(item) -> None:
    print()
    print(f"===== {item.relative_path} [{item.role}] =====")
    if item.text is None:
        print("[text not captured]")
        return
    lines = item.text.splitlines()
    for number, line in enumerate(lines, start=1):
        print(f"{number:04d}: {line}")
    if item.truncated:
        print("[TRUNCATED: increase --max-lines if more context is needed]")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = inspect_saturn_standalone_template(
            args.candidate,
            max_text_lines=args.max_lines,
        )
    except Exception as exc:
        print(
            f"srk-saturn-standalone-template: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK standalone Saturn template probe")
    print("-" * 44)
    print(f"Candidate     : {report.directory}")
    print("Access policy : READ-ONLY inspection; no files or PATH are modified")
    print()

    print("File inventory")
    print("--------------")
    for item in report.files:
        print(
            f"{item.role:<16} {item.size:>9} bytes  "
            f"{item.sha256}  {item.relative_path}"
        )

    print()
    print("IP.BIN metadata")
    print("---------------")
    if report.ip_bin is None:
        print("[none in candidate directory]")
    else:
        print(f"Path: {report.ip_bin}")
        for key, value in report.ip_metadata:
            print(f"{key:<14}: {value}")

    print()
    print("Reviewed text")
    print("-------------")
    reviewed = [item for item in report.files if item.text is not None]
    if not reviewed:
        print("[none]")
    for item in reviewed:
        _print_text_file(item)

    print()
    print("Interpretation")
    print("--------------")
    print(
        "This is source/build evidence only. It does not modify, copy, compile, "
        "link, package, or execute the candidate."
    )
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
