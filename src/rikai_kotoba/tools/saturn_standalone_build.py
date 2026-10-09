"""Build a generated SRK standalone Saturn project with Python orchestration."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.standalone_build import (
    build_saturn_standalone_project,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-standalone-build",
        description=(
            "Build one fresh SRK-generated Saturn diagnostics project using "
            "Python-native orchestration. SH-ELF gcc/as and mkisofs remain the "
            "code-generation/package backends; make and shell build logic are not used. "
            "The final deployable image is a verified MODE1/2352 BIN/CUE pair."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Fresh SRK-generated standalone project directory",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = build_saturn_standalone_project(args.project)
    except Exception as exc:
        print(
            f"srk-saturn-standalone-build: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK Python-native standalone Saturn build")
    print("-" * 45)
    print(f"Project : {result.project_root}")
    print(f"Log     : {result.log_path}")
    print(f"Report  : {result.report_path}")
    print()

    print("Commands")
    for command in result.commands:
        print(f"  [{command.returncode}] {command.label}")
        if command.output.strip():
            for line in command.output.rstrip().splitlines():
                print(f"      {line}")

    print()
    if result.artifacts:
        print("Artifacts")
        for artifact in result.artifacts:
            relative = artifact.path.relative_to(result.project_root)
            print(
                f"  {relative}  {artifact.size} bytes  SHA-256 {artifact.sha256}"
            )
    else:
        print("Artifacts: [none]")

    print()
    if result.successful:
        deploy = result.project_root / "build" / "SRK-Diagnostics"
        print("Build result: SUCCESS")
        print("Orchestration: Python-native; shell=False; PATH unchanged.")
        print("Deployable image: verified single-track MODE1/2352 BIN/CUE")
        print(f"Deploy folder   : {deploy}")
        print("No BIN/CUE image was copied to SAROO or physical Saturn hardware.")
        return 0

    print("Build result: FAILED")
    print("Review the build log/report; use a fresh generated project for the next attempt.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
