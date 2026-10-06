"""Command-line interface for SRK (Salix Rikai Kotoba)."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional, Sequence, Tuple

from rikai_kotoba.core.disc_source import open_disc_source
from rikai_kotoba.core.iso9660 import ISO9660Entry, ISO9660Reader
from rikai_kotoba.core.safe_extractor import ExtractionReport, ISOExtractor
from rikai_kotoba.formats.saturn.ip_bin import parse_ip_bin


def _open_iso(path: os.PathLike[str] | str) -> Tuple[object, ISO9660Reader]:
    source = open_disc_source(path)
    return source, ISO9660Reader(source)


def _entry_rows(
    reader: ISO9660Reader,
    *,
    root_only: bool,
) -> Iterable[Tuple[str, ISO9660Entry]]:
    if root_only:
        for entry in reader.list_root_directory():
            yield f"/{entry.name}", entry
    else:
        yield from reader.walk()


def _print_extraction_report(report: ExtractionReport) -> None:
    print(
        "Extraction summary: "
        f"{report.extracted_count} files extracted, "
        f"{report.directory_count} directories, "
        f"{report.skipped_count} existing files skipped, "
        f"{report.error_count} errors."
    )
    for item in report.items:
        if item.status == "error":
            print(
                f"  ERROR {item.iso_path}: "
                f"{item.error_type}: {item.error_message}"
            )


def _cmd_list_files(args: argparse.Namespace) -> int:
    _source, reader = _open_iso(args.path)
    rows = list(_entry_rows(reader, root_only=args.root_only))

    print(f"Disc image: {os.path.abspath(args.path)}")
    print(f"Entries: {len(rows)}")
    print()
    print(f"{'Type':<6} {'LBA':<10} {'Size':<12} Path")
    print("-" * 72)
    for path, entry in rows:
        kind = "DIR" if entry.is_dir else "FILE"
        print(f"{kind:<6} 0x{entry.lba:08X} {entry.size:<12} {path}")
    return 0


def _cmd_inspect_saturn(args: argparse.Namespace) -> int:
    source = open_disc_source(args.path)
    metadata = parse_ip_bin(source)

    print(f"Sega Saturn image: {os.path.abspath(args.path)}")
    print()
    print("Saturn IP.BIN metadata")
    print("-" * 40)
    for key, value in metadata.items():
        print(f"{key.replace('_', ' ').title():<18}: {value}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    _source, reader = _open_iso(args.path)
    extractor = ISOExtractor(reader)

    if args.file:
        result = extractor.extract_file(
            args.file,
            args.output,
            overwrite=args.overwrite,
        )
        print(f"Extracted {result.iso_path} -> {result.output_path}")
        return 0

    report = extractor.extract_all(
        args.output,
        overwrite=args.overwrite,
        continue_on_error=not args.fail_fast,
    )
    _print_extraction_report(report)
    return 1 if report.error_count and args.fail_on_errors else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk",
        description=(
            "SRK (Salix Rikai Kotoba) - generic retro-disc localization and "
            "reverse-engineering toolkit"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list-files",
        help="List ISO-9660 files from a CUE or standalone disc image",
    )
    list_parser.add_argument("path", help="Path to .cue/.bin/.img/.iso/.raw input")
    list_parser.add_argument(
        "--root-only",
        action="store_true",
        help="List only the ISO root directory instead of walking recursively",
    )
    list_parser.set_defaults(handler=_cmd_list_files)

    saturn_parser = subparsers.add_parser(
        "inspect-saturn",
        help="Read Sega Saturn IP.BIN metadata from logical LBA 0",
    )
    saturn_parser.add_argument("path", help="Path to .cue/.bin/.img/.iso/.raw input")
    saturn_parser.set_defaults(handler=_cmd_inspect_saturn)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Safely extract ISO-9660 content without modifying the source image",
    )
    extract_parser.add_argument("path", help="Path to .cue/.bin/.img/.iso/.raw input")
    extract_parser.add_argument("output", help="Destination directory")
    extract_parser.add_argument(
        "--file",
        metavar="ISO_PATH",
        help="Extract one ISO path instead of the complete reachable tree",
    )
    extract_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing destination files explicitly",
    )
    extract_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on the first extraction error",
    )
    extract_parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Return a non-zero exit status if a tree extraction records errors",
    )
    extract_parser.set_defaults(handler=_cmd_extract)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    try:
        return int(handler(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"srk: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
