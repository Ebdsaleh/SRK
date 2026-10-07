"""Developer-facing SAROO SH-ELF toolchain preflight command."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.saroo.toolchain import inspect_saroo_toolchain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saroo-toolchain",
        description=(
            "Read-only preflight for the SH-ELF tools required by upstream "
            "SAROO Firm_Saturn. This command does not modify PATH, build, or flash firmware."
        ),
    )
    parser.add_argument(
        "--toolchain-root",
        default=None,
        help=(
            "Optional SaturnOrbit/toolchain directory to search before PATH. "
            "Nested bin directories are searched automatically."
        ),
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = inspect_saroo_toolchain(args.toolchain_root)
    except Exception as exc:
        print(f"srk-saroo-toolchain: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print("SAROO Firm_Saturn toolchain preflight")
    print("-" * 44)
    if report.search_root is None:
        print("Explicit root : [not supplied]")
    else:
        print(f"Explicit root : {report.search_root}")
    print("PATH policy   : read-only fallback; PATH is not modified")
    print()

    for probe in report.probes:
        if probe.available:
            print(
                f"[OK]      {probe.requirement.name:<16} "
                f"{probe.resolved_path} ({probe.source})"
            )
        else:
            print(
                f"[MISSING] {probe.requirement.name:<16} "
                f"{probe.requirement.purpose}"
            )

    print()
    if report.ready:
        print("Discovery result: READY - every required executable was resolved.")
        print("A real Firm_Saturn build is still required to prove the installation works.")
        return 0

    print("Discovery result: NOT READY")
    print("Missing: " + ", ".join(report.missing))
    print(
        "Point --toolchain-root at the SaturnOrbit/SH-ELF toolchain location "
        "or make the required tools available on PATH."
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
