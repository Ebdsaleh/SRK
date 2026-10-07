"""Controlled developer-facing SAROO Firm_Saturn build command."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo import build_firm_saturn_tree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-build",
        description=(
            "Clean and build an SRK-generated SAROO Firm_Saturn tree using an "
            "explicit SaturnOrbit/SH-ELF toolchain root. The child build gets "
            "a process-local PATH only; this command does not deploy or flash firmware."
        ),
    )
    parser.add_argument(
        "generated_root",
        help="SRK-generated SAROO-SRK root containing SRK_INTEGRATION.txt",
    )
    parser.add_argument(
        "--toolchain-root",
        required=True,
        help="Verified SaturnOrbit/SH-ELF root used for the controlled build",
    )
    parser.add_argument(
        "--log",
        default=None,
        help=(
            "Optional new build-log path. If omitted, SRK allocates a unique "
            "SRK_BUILD_LOG*.txt beneath the generated tree."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = build_firm_saturn_tree(
            args.generated_root,
            args.toolchain_root,
            log_path=args.log,
        )
    except Exception as exc:
        print(f"srk-saroo-build: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SRK controlled SAROO Firm_Saturn build")
    print("-" * 44)
    print(f"Generated root : {result.generated_root}")
    print(f"Firm_Saturn    : {result.firm_saturn_directory}")
    print(f"Toolchain root : {result.toolchain_root}")
    print(f"Build log      : {result.log_path}")
    print(f"Clean exit     : {result.clean_returncode}")
    if result.build_returncode is None:
        print("Build exit     : [not run; clean failed]")
    else:
        print(f"Build exit     : {result.build_returncode}")
    print()

    if result.artifacts:
        print("Artifacts:")
        for artifact in result.artifacts:
            print(
                f"  {artifact.path.name:<12} {artifact.size:>10} bytes  "
                f"SHA-256 {artifact.sha256}"
            )
    else:
        print("Artifacts: [none of the expected outputs were produced]")

    print()
    if result.successful:
        print("Build result: SUCCESS")
        print("No firmware was copied to SD or flashed.")
        return 0

    print("Build result: FAILED")
    print("Review the captured build log above; no firmware was deployed or flashed.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
