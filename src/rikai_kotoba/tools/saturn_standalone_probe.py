"""Developer-facing read-only probe for standalone Saturn build assets."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from rikai_kotoba.hardware.saturn.standalone_environment import (
    inspect_saturn_standalone_environment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-standalone-probe",
        description=(
            "Read-only discovery of the compiler, SGL, sample, IP.BIN, and image "
            "construction assets available beneath an explicit Saturn development root."
        ),
    )
    parser.add_argument(
        "--saturn-root",
        required=True,
        help="SaturnOrbit/Saturn development root to inspect without modifying it",
    )
    return parser


def _print_paths(label: str, paths: tuple[object, ...], *, limit: int = 25) -> None:
    print(f"{label}: {len(paths)}")
    for path in paths[:limit]:
        print(f"  {path}")
    if len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report = inspect_saturn_standalone_environment(args.saturn_root)
    except Exception as exc:
        print(
            f"srk-saturn-standalone-probe: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    print("SRK standalone Saturn environment probe")
    print("-" * 44)
    print(f"Saturn root   : {report.root}")
    print("Access policy : READ-ONLY discovery; no files or PATH are modified")
    print()

    print("SH-ELF compiler tools")
    print("---------------------")
    for probe in report.compiler.probes:
        if probe.available:
            print(
                f"[OK]      {probe.requirement.name:<16} "
                f"{probe.resolved_path} ({probe.source})"
            )
        else:
            print(f"[MISSING] {probe.requirement.name:<16} {probe.requirement.purpose}")
    print()

    print("Standalone SDK/template evidence")
    print("--------------------------------")
    _print_paths("SGL_302j roots", report.sgl_roots)
    _print_paths("SGL headers", report.sgl_headers)
    _print_paths("Static libraries", report.libraries)
    _print_paths("Sample Makefiles", report.sample_makefiles)
    _print_paths("IP.BIN assets", report.ip_bin_assets)
    print()

    print("Build/image helper tools")
    print("------------------------")
    for probe in report.tools:
        if probe.available:
            print(
                f"[FOUND]   {probe.requirement.key:<16} "
                f"{probe.resolved_path} ({probe.source})"
            )
        else:
            print(
                f"[MISSING] {probe.requirement.key:<16} "
                f"{probe.requirement.purpose}"
            )
    print()

    print("Assessment")
    print("----------")
    print(f"Compiler set     : {'READY' if report.compiler_ready else 'NOT READY'}")
    print(f"SGL tree         : {'FOUND' if report.sgl_detected else 'NOT CONFIRMED'}")
    print(f"Sample templates : {'FOUND' if report.samples_detected else 'NOT CONFIRMED'}")
    print(f"IP.BIN asset     : {'FOUND' if report.ip_asset_detected else 'NOT CONFIRMED'}")
    print()
    print(
        "This probe does not claim that a standalone image can already be built. "
        "Its purpose is to select a concrete, locally available build/template path "
        "before SRK creates any generated standalone project."
    )
    print("No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
