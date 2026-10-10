"""Mjolnir binary/archive reverse-engineering workbench.

This mode complements Mjolnir's disc/ISO workflow with read-only inspection of
object files, static-library archives, symbols, and cross-library dependencies.
It performs its own ELF/COFF parsing and never invokes compiler/binutils tools.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional, Sequence

from rikai_kotoba.core.binary_archive import (
    BinaryArchiveError,
    BinaryInspectionReport,
    inspect_binary,
)
from rikai_kotoba.core.binary_index import (
    BinarySymbolIndex,
    build_symbol_index,
    discover_binary_candidates,
    find_symbols,
    library_dependency_edges,
)
from rikai_kotoba.core.object_file import (
    ObjectFormatError,
    inspect_archive_objects,
    inspect_object_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-mjolnir-binary",
        description=(
            "Read-only Mjolnir binary/archive workbench: container layout, "
            "ELF/COFF objects, symbols, searches, and dependency resolution."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Binary/archive files or directories to inspect read-only.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively scan binary/object/archive candidates under directories.",
    )
    parser.add_argument(
        "--member-limit",
        type=int,
        default=200,
        help="Maximum member rows printed per archive (default: 200).",
    )
    parser.add_argument(
        "--symbol-limit",
        type=int,
        default=200,
        help="Maximum symbols printed per object/search group (default: 200).",
    )
    parser.add_argument(
        "--symbols",
        action="store_true",
        help="Print external defined/undefined symbols for every decoded object.",
    )
    parser.add_argument(
        "--dependencies",
        action="store_true",
        help="Resolve undefined symbols against all scanned inputs and print dependency edges.",
    )
    parser.add_argument(
        "--search-symbol",
        action="append",
        default=[],
        metavar="TEXT",
        help="Search symbol names across all inputs; may be supplied more than once.",
    )
    parser.add_argument(
        "--exact-symbol",
        action="store_true",
        help="Make --search-symbol require exact names instead of substring matches.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enable symbol tables and dependency resolution in one pass.",
    )
    return parser


def _print_report(report: BinaryInspectionReport, member_limit: int) -> None:
    print("=" * 78)
    print("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR")
    print("=" * 78)
    print(f"Source       : {report.path}")
    print("Read-only    : yes")
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


def _print_object_summary(path: Path) -> None:
    try:
        report = inspect_binary(path)
        if report.container_kind == "unix-ar":
            records = inspect_archive_objects(path)
            decoded = [record for record in records if record.object is not None]
            failed = [record for record in records if record.object is None]
            if decoded:
                formats: dict[str, int] = {}
                sections = 0
                symbols = 0
                for record in decoded:
                    assert record.object is not None
                    formats[record.object.format_name] = formats.get(record.object.format_name, 0) + 1
                    sections += len(record.object.sections)
                    symbols += len(record.object.symbols)
                format_text = ", ".join(f"{name}={count}" for name, count in sorted(formats.items()))
                print(
                    f"Object decode : {len(decoded)} decoded ({format_text}); "
                    f"{sections} sections; {symbols} symbols"
                )
            if failed:
                print(f"Object errors : {len(failed)} payload member(s) unsupported/malformed")
            return
        obj = inspect_object_file(path)
        print(
            f"Object decode : {obj.format_name} {obj.architecture} {obj.byte_order}-endian; "
            f"{len(obj.sections)} sections; {len(obj.symbols)} symbols"
        )
    except (OSError, BinaryArchiveError, ObjectFormatError):
        return


def _print_symbols(index: BinarySymbolIndex, limit: int) -> None:
    print("\n" + "=" * 78)
    print("MJOLNIR OBJECT SYMBOL TABLES")
    print("=" * 78)
    for unit in index.units:
        defined = unit.object.defined_symbols
        undefined = unit.object.undefined_symbols
        print(f"{unit.display_name}")
        print(
            f"  format={unit.object.format_name} arch={unit.object.architecture} "
            f"sections={len(unit.object.sections)} defined={len(defined)} undefined={len(undefined)}"
        )
        rows = [("DEF", symbol) for symbol in defined] + [("UND", symbol) for symbol in undefined]
        for status, symbol in rows[:limit]:
            weak = " weak" if symbol.weak else ""
            print(
                f"    {status:<3} {symbol.name:<40} section={symbol.section:<12} "
                f"kind={symbol.kind}{weak}"
            )
        if len(rows) > limit:
            print(f"    ... {len(rows) - limit} symbols omitted by --symbol-limit")


def _print_dependency_report(index: BinarySymbolIndex) -> None:
    print("\n" + "=" * 78)
    print("MJOLNIR SYMBOL DEPENDENCY ANALYSIS")
    print("=" * 78)
    print(f"Decoded objects : {len(index.units)}")
    print(f"Provider names  : {len(index.providers)}")
    print(f"Consumer names  : {len(index.consumers)}")
    print(f"Unresolved uses : {len(index.unresolved)}")

    edges = library_dependency_edges(index)
    if edges:
        print("\nResolved source-file dependency edges:")
        for (consumer, provider), symbols in edges.items():
            print(f"  {consumer}")
            print(f"    -> {provider}")
            preview = ", ".join(symbols[:20])
            print(f"       symbols ({len(symbols)}): {preview}")
            if len(symbols) > 20:
                print(f"       ... {len(symbols) - 20} more")
    else:
        print("\nResolved source-file dependency edges: none")

    if index.unresolved:
        print("\nUnresolved external symbols:")
        grouped: dict[str, list[str]] = {}
        for dependency in index.unresolved:
            grouped.setdefault(dependency.symbol, []).append(dependency.consumer.display_name)
        for symbol, consumers in sorted(grouped.items()):
            print(f"  {symbol}")
            for consumer in consumers[:8]:
                print(f"    <- {consumer}")
            if len(consumers) > 8:
                print(f"    ... {len(consumers) - 8} more consumers")
    else:
        print("\nUnresolved external symbols: none")

    if index.errors:
        print("\nScan warnings:")
        for error in index.errors:
            print(f"  {error.path}: {error.detail}")


def _print_symbol_search(index: BinarySymbolIndex, query: str, exact: bool, limit: int) -> None:
    matches = find_symbols(index, query, exact=exact)
    print("\n" + "=" * 78)
    mode = "exact" if exact else "substring"
    print(f"MJOLNIR SYMBOL SEARCH: {query!r} ({mode})")
    print("=" * 78)
    if not matches:
        print("No matching symbol names.")
        return
    for name, providers, consumers in matches[:limit]:
        print(f"{name}: providers={len(providers)} consumers={len(consumers)}")
        for location in providers[:8]:
            print(f"  DEF {location.display_name} [{location.object_format}]")
        for location in consumers[:8]:
            print(f"  UND {location.display_name} [{location.object_format}]")
    if len(matches) > limit:
        print(f"... {len(matches) - limit} matching names omitted by --symbol-limit")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.member_limit <= 0 or args.symbol_limit <= 0:
        print("[-] --member-limit and --symbol-limit must be positive")
        return 2

    explicit = [Path(path).expanduser().resolve(strict=False) for path in args.paths]
    missing = [path for path in explicit if not path.exists()]
    if missing:
        for path in missing:
            print("=" * 78)
            print("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR")
            print("=" * 78)
            print(f"Source       : {path}")
            print("Read-only    : yes")
            print("Result       : ERROR: input path does not exist")
        return 2

    candidates = discover_binary_candidates(explicit, recursive=args.recursive)
    if not candidates:
        print("[-] No supported binary/object/archive candidates found.")
        return 2

    failed = False
    for index, path in enumerate(candidates):
        if index:
            print("")
        try:
            report = inspect_binary(os.path.abspath(os.fspath(path)))
        except (BinaryArchiveError, OSError) as exc:
            print("=" * 78)
            print("SRK MJOLNIR BINARY / ARCHIVE INSPECTOR")
            print("=" * 78)
            print(f"Source       : {path}")
            print("Read-only    : yes")
            print(f"Result       : ERROR: {type(exc).__name__}: {exc}")
            failed = True
            continue
        _print_report(report, args.member_limit)
        _print_object_summary(path)

    need_index = args.symbols or args.dependencies or args.search_symbol or args.all
    if need_index:
        index = build_symbol_index(explicit, recursive=args.recursive)
        if args.symbols or args.all:
            _print_symbols(index, args.symbol_limit)
        if args.dependencies or args.all:
            _print_dependency_report(index)
        for query in args.search_symbol:
            _print_symbol_search(index, query, args.exact_symbol, args.symbol_limit)

    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
