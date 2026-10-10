"""Read-only Mjolnir binary/archive inspection mode.

This companion entry point extends Mjolnir beyond disc containers without
changing the existing interactive disc workflow.  It inspects one or more
binary/archive files directly from Python and never writes, extracts, or invokes
external compiler/binutils tools.
"""

from __future__ import annotations

import argparse
import os
from typing import Optional, Sequence

from rikai_kotoba.core.binary_archive import (
    BinaryArchiveError,
    BinaryInspectionReport,
    inspect_binary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-mjolnir-binary",
        description=(
            "Read-only Mjolnir binary/archive inspector. Reports container "
            "structure, member offsets, hashes, and conservative signatures."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Binary/archive files to inspect read-only.",
    )
    parser.add_argument(
        "--member-limit",
        type=int,
        default=200,
        help="Maximum member rows printed per archive (default: 200).",
    )
    return parser


def _print_report(report: BinaryInspectionReport, member_limit: int) -> None:
    print("=" * 78)
    print("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR")
    print("=" * 78)
    print(f"Source       : {report.path}")
    print(f"Read-only    : yes")
    print(f"Size         : {report.size} bytes")
    print(f"SHA-256      : {report.sha256}")
    print(f"Container    : {report.container_kind}")
    print(f"Signature    : {report.signature.kind}")
    print(f"Detail       : {report.signature.detail}")
    print(f"Prefix hex   : {report.signature.prefix_hex}")
    print(f"Prefix ASCII : {report.signature.prefix_ascii}")
    print(f"Members      : {len(report.members)}")

    if not report.members:
        return

    print("-" * 78)
    for member in report.members[:member_limit]:
        role = "metadata" if member.metadata else "payload"
        print(f"[{member.index:03d}] {member.name}")
        print(f"      role          : {role}")
        print(f"      raw name      : {member.raw_name}")
        print(f"      header offset : 0x{member.header_offset:08X}")
        print(f"      data offset   : 0x{member.data_offset:08X}")
        print(f"      stored size   : {member.stored_size}")
        print(f"      payload size  : {member.size}")
        print(f"      SHA-256       : {member.sha256}")
        print(f"      format        : {member.signature.kind}")
        print(f"      detail        : {member.signature.detail}")
        print(f"      prefix hex    : {member.signature.prefix_hex}")
        print(f"      prefix ASCII  : {member.signature.prefix_ascii}")

    omitted = len(report.members) - member_limit
    if omitted > 0:
        print(f"... {omitted} additional members omitted by --member-limit")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.member_limit <= 0:
        print("[-] --member-limit must be positive")
        return 2

    failed = False
    for index, path in enumerate(args.paths):
        if index:
            print("")
        try:
            report = inspect_binary(os.path.abspath(os.fspath(path)))
        except (BinaryArchiveError, OSError) as exc:
            print("=" * 78)
            print("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR")
            print("=" * 78)
            print(f"Source       : {os.path.abspath(os.fspath(path))}")
            print("Read-only    : yes")
            print(f"Result       : ERROR: {type(exc).__name__}: {exc}")
            failed = True
            continue
        _print_report(report, args.member_limit)

    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
