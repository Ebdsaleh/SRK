"""Command-line interface for SRK (Salix Rikai Kotoba)."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, Optional, Sequence, Tuple

from rikai_kotoba.application.paths import default_saroo_dump_directory
from rikai_kotoba.core.correlation import correlate_file_to_memory_dump
from rikai_kotoba.core.disc_source import open_disc_source
from rikai_kotoba.core.iso9660 import ISO9660Entry, ISO9660Reader
from rikai_kotoba.core.safe_extractor import ExtractionReport, ISOExtractor
from rikai_kotoba.formats.saturn.ip_bin import parse_ip_bin
from rikai_kotoba.hardware.saturn.saroo import (
    CaptureStore,
    build_firm_saturn_tree,
    import_raw_sd_dump,
    inspect_saroo_sd_layout,
    prepare_firm_saturn_tree,
    verify_capture,
)


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


def _parse_address(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        raise argparse.ArgumentTypeError("address must not be empty")
    try:
        parsed = int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "address must be decimal or 0x-prefixed hexadecimal"
        ) from exc
    if parsed < 0 or parsed >= (1 << 32):
        raise argparse.ArgumentTypeError("address must fit in 32 bits")
    return parsed


def _parse_positive_integer(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        raise argparse.ArgumentTypeError("value must not be empty")
    try:
        parsed = int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "value must be decimal or 0x-prefixed hexadecimal"
        ) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


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


def _cmd_correlate(args: argparse.Namespace) -> int:
    report = correlate_file_to_memory_dump(
        args.source,
        args.dump,
        memory_base_address=args.base_address,
        chunk_size=args.chunk_size,
        minimum_chunk_size=args.minimum_chunk_size,
        maximum_occurrences_per_chunk=args.max_occurrences,
    )

    print(f"Source file : {report.source_path}")
    print(f"Memory dump : {report.memory_dump_path}")
    print(f"Memory base : 0x{report.memory_base_address:08X}")
    print(f"Source SHA-256: {report.source_sha256}")
    print(f"Dump SHA-256  : {report.memory_dump_sha256}")
    print(
        "Chunks      : "
        f"{report.scanned_chunks} scanned, "
        f"{report.matched_chunks} matched, "
        f"{report.ambiguous_chunks} ambiguous"
    )
    print()

    if not report.runs:
        print("No exact provenance runs were found.")
        return 0

    print(f"{'Source offset':<15} {'Memory address':<16} {'Length':<12} Chunks")
    print("-" * 60)
    for run in report.runs:
        print(
            f"0x{run.source_offset:08X}    "
            f"0x{run.memory_address:08X}     "
            f"0x{run.length:08X}   "
            f"{run.chunk_count}"
        )
    return 0


def _cmd_import_saroo_dump(args: argparse.Namespace) -> int:
    capture_root = args.capture_root or str(default_saroo_dump_directory())
    store = CaptureStore(capture_root)
    artifact = import_raw_sd_dump(
        args.dump,
        base_address=args.base_address,
        checkpoint=args.checkpoint,
        store=store,
        label=args.label,
        session_label=args.session_label,
        expected_size=args.expected_size,
    )
    verification = verify_capture(artifact.directory)
    verification.require_valid()

    print(f"Imported raw dump : {os.path.abspath(args.dump)}")
    print(f"Saturn base       : 0x{args.base_address:08X}")
    print(f"Capture directory : {artifact.directory}")
    print(f"Manifest          : {artifact.manifest_path}")
    for path in artifact.region_paths:
        print(f"Region file       : {path}")
    print("Integrity         : verified")
    return 0


def _cmd_inspect_saroo_sd(args: argparse.Namespace) -> int:
    report = inspect_saroo_sd_layout(args.path)

    print("SAROO SD-card layout inspection")
    print("-" * 44)
    print(f"Card root       : {report.root}")
    print(f"Layout          : {report.layout}")
    print("Access policy   : read-only inspection")
    print()

    if report.firmware_files:
        print("Recognised Saturn firmware:")
        for firmware in report.firmware_files:
            print(f"  {firmware.relative_path}")
            print(f"    Size     : {firmware.size} bytes")
            print(f"    SHA-256  : {firmware.sha256}")
    else:
        print("Recognised Saturn firmware: [none]")

    print()
    print("Companion layout evidence:")
    print(f"  SAROO directory : {'present' if report.saroo_directory_present else 'missing'}")
    print(f"  mcuapp.bin      : {'present' if report.mcuapp_present else 'missing'}")
    print(f"  saroocfg.txt    : {'present' if report.config_present else 'missing'}")
    print(f"  ISO directory   : {'present' if report.iso_directory_present else 'missing'}")
    print(f"  update directory: {'present' if report.update_directory_present else 'missing'}")

    if report.warnings:
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")

    print()
    print("No files were modified.")
    return 0 if report.recognized else 2


def _cmd_prepare_saroo_firmware(args: argparse.Namespace) -> int:
    result = prepare_firm_saturn_tree(args.source, args.output)
    print(f"Source SAROO tree : {result.source_root}")
    print(f"Generated tree    : {result.output_root}")
    print(f"Firm_Saturn       : {result.firm_saturn_directory}")
    print(f"Patched Makefile  : {result.makefile_path}")
    print(f"Patched shell     : {result.shell_path}")
    print(f"Capture helper    : {result.helper_source_path}")
    print("Original SAROO source was not modified.")
    print("Development shell commands: srkwl, srkwh")
    return 0


def _cmd_build_saroo_firmware(args: argparse.Namespace) -> int:
    result = build_firm_saturn_tree(
        args.generated_root,
        args.toolchain_root,
        log_path=args.log,
    )

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

    correlate_parser = subparsers.add_parser(
        "correlate",
        help="Find exact source-file chunks inside a raw Saturn memory dump",
    )
    correlate_parser.add_argument("source", help="Extracted/source file to correlate")
    correlate_parser.add_argument("dump", help="Raw captured memory-region file")
    correlate_parser.add_argument(
        "--base-address",
        required=True,
        type=_parse_address,
        help="Saturn address represented by dump offset 0 (decimal or 0x-prefixed hex)",
    )
    correlate_parser.add_argument(
        "--chunk-size",
        type=int,
        default=4096,
        help="Exact comparison chunk size in bytes (default: 4096)",
    )
    correlate_parser.add_argument(
        "--minimum-chunk-size",
        type=int,
        default=64,
        help="Minimum final chunk size worth correlating (default: 64)",
    )
    correlate_parser.add_argument(
        "--max-occurrences",
        type=int,
        default=8,
        help="Suppress chunks repeated more than this many times in RAM (default: 8)",
    )
    correlate_parser.set_defaults(handler=_cmd_correlate)

    import_parser = subparsers.add_parser(
        "import-saroo-dump",
        help="Import a raw SAROO SD-card memory dump into a verified SRK capture",
    )
    import_parser.add_argument("dump", help="Raw dump file copied from the SAROO SD card")
    import_parser.add_argument(
        "--base-address",
        required=True,
        type=_parse_address,
        help="Saturn address represented by raw dump offset 0",
    )
    import_parser.add_argument(
        "--checkpoint",
        required=True,
        help="Human-readable capture checkpoint, for example title-screen",
    )
    import_parser.add_argument(
        "--capture-root",
        default=None,
        help="Destination root for verified captures; defaults to SRK-Workspace/Dumps/SAROO",
    )
    import_parser.add_argument(
        "--label",
        default="",
        help="Optional memory-region label such as work_ram_high",
    )
    import_parser.add_argument(
        "--session-label",
        default="",
        help="Optional session label stored in capture metadata",
    )
    import_parser.add_argument(
        "--expected-size",
        default=None,
        type=_parse_positive_integer,
        help="Reject the import unless the raw file has exactly this many bytes",
    )
    import_parser.set_defaults(handler=_cmd_import_saroo_dump)

    inspect_saroo_sd_parser = subparsers.add_parser(
        "inspect-saroo-sd",
        help="Read-only inspection of a mounted SAROO SD-card firmware layout",
    )
    inspect_saroo_sd_parser.add_argument(
        "path",
        help="Root directory of the mounted SAROO SD card",
    )
    inspect_saroo_sd_parser.set_defaults(handler=_cmd_inspect_saroo_sd)

    prepare_parser = subparsers.add_parser(
        "prepare-saroo-firmware",
        help="Create a separate SRK-enabled copy of SAROO's Firm_Saturn source",
    )
    prepare_parser.add_argument(
        "source",
        help="Root of an upstream SAROO checkout containing Firm_Saturn/",
    )
    prepare_parser.add_argument(
        "output",
        help="New output directory; must not already exist or be inside the source checkout",
    )
    prepare_parser.set_defaults(handler=_cmd_prepare_saroo_firmware)

    build_saroo_parser = subparsers.add_parser(
        "build-saroo-firmware",
        help="Clean and build an SRK-generated SAROO Firm_Saturn tree",
    )
    build_saroo_parser.add_argument(
        "generated_root",
        help="SRK-generated SAROO-SRK root containing SRK_INTEGRATION.txt",
    )
    build_saroo_parser.add_argument(
        "--toolchain-root",
        required=True,
        help="Verified SaturnOrbit/SH-ELF root used for the controlled build",
    )
    build_saroo_parser.add_argument(
        "--log",
        default=None,
        help=(
            "Optional new build-log path. If omitted, SRK allocates a unique "
            "SRK_BUILD_LOG*.txt beneath the generated tree."
        ),
    )
    build_saroo_parser.set_defaults(handler=_cmd_build_saroo_firmware)

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
