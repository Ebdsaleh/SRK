"""Mjolnir: interactive, game-agnostic SRK disc and hex research utility.

Mjolnir delegates disc geometry, CUE mapping, ISO-9660 parsing, extraction, and
hex formatting to SRK core modules. Input media is always opened read-only.

Examples after installing SRK::

    srk-mjolnir /path/to/disc.cue
    srk-mjolnir /path/to/disc-images --output-dir /path/to/workspace

With no source argument, Mjolnir searches the current working directory when
option 0 is selected. No repository-relative game or image path is assumed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
import shutil
import tempfile
from typing import Callable, List, Optional, Sequence, Tuple

from rikai_kotoba.core.disc_source import (
    discover_disc_candidates,
    open_disc_source,
)
from rikai_kotoba.core.hex_dump import iter_hexdump_lines, write_hexdump
from rikai_kotoba.core.iso9660 import ISO9660Entry, ISO9660Reader
from rikai_kotoba.core.safe_extractor import ExtractionReport, ISOExtractor


@dataclass
class DiscSession:
    source_path: str
    source: object
    reader: ISO9660Reader
    extractor: ISOExtractor
    entries: List[Tuple[str, ISO9660Entry]]
    base_name: str


@dataclass(frozen=True)
class OutputWriteResult:
    """Result of an interactive Mjolnir output-write decision."""

    output_path: str
    action: str
    backup_path: Optional[str] = None


def open_disc(path: os.PathLike[str] | str) -> DiscSession:
    """Open a supported disc source as a read-only Mjolnir session."""

    source_path = os.path.abspath(os.fspath(path))
    source = open_disc_source(source_path)
    reader = ISO9660Reader(source)
    entries = list(reader.walk())
    return DiscSession(
        source_path=source_path,
        source=source,
        reader=reader,
        extractor=ISOExtractor(reader),
        entries=entries,
        base_name=os.path.splitext(os.path.basename(source_path))[0],
    )


def _resolve_startup_source(
    source_path: Optional[os.PathLike[str] | str],
) -> Tuple[str, Optional[DiscSession]]:
    """Resolve a CLI source into an image-search root and optional open session."""

    if source_path is None:
        return os.path.abspath(os.getcwd()), None

    path = os.path.abspath(os.fspath(source_path))
    if os.path.isdir(path):
        return path, None
    if os.path.isfile(path):
        return os.path.dirname(path), open_disc(path)
    raise FileNotFoundError(f"Input path not found: {path}")


def _non_directory_entries(
    entries: Sequence[Tuple[str, ISO9660Entry]],
) -> List[Tuple[str, ISO9660Entry]]:
    return [(path, entry) for path, entry in entries if not entry.is_dir]


def select_target_file(
    entries: Sequence[Tuple[str, ISO9660Entry]],
) -> Optional[Tuple[str, ISO9660Entry]]:
    """Interactive paged file selection with index and name/path search."""

    files = _non_directory_entries(entries)
    if not files:
        print("[-] No files found on the loaded image.")
        return None

    page = 0
    page_size = 25
    total = len(files)
    total_pages = (total + page_size - 1) // page_size

    while True:
        start = page * page_size
        end = min(start + page_size, total)

        print(
            f"\n[+] Select a file "
            f"(Page {page + 1}/{total_pages} | {total} total files):"
        )
        print(f"{'Index':<7} | {'Path':<45} | {'Size (Bytes)'}")
        print("-" * 78)
        for index in range(start, end):
            path, entry = files[index]
            print(f"[{index:<4}] | {path:<45} | {entry.size}")
        print("-" * 78)

        nav: List[str] = []
        if page < total_pages - 1:
            nav.append("[N]ext")
        if page > 0:
            nav.append("[B]ack")
        else:
            nav.append("[B]ack (Cancel)")

        choice = input(
            f"Enter file index [0-{total - 1}], "
            f"{' / '.join(nav)}, or name search: "
        ).strip()

        lowered = choice.lower()
        if lowered in ("n", "next"):
            if page < total_pages - 1:
                page += 1
            else:
                print("[-] Already on the last page.")
            continue

        if lowered in ("b", "back"):
            if page > 0:
                page -= 1
            else:
                print("[+] Selection cancelled.")
                return None
            continue

        if choice.isdigit():
            index = int(choice)
            if 0 <= index < total:
                selected = files[index]
                print(f"[+] Selected active file: {selected[0]}")
                return selected
            print(f"[-] Index out of range [0-{total - 1}].")
            continue

        query = choice.casefold()
        exact = [
            item
            for item in files
            if item[1].name.casefold() == query
            or item[0].casefold() == query
            or item[1].raw_name.casefold() == query
        ]
        if len(exact) == 1:
            print(f"[+] Selected active file: {exact[0][0]}")
            return exact[0]

        partial = [item for item in files if query in item[0].casefold()]
        if len(partial) == 1:
            print(f"[+] Selected active file: {partial[0][0]}")
            return partial[0]
        if len(partial) > 1:
            print(f"[-] Multiple files match '{choice}':")
            for path, _entry in partial:
                print(f"    - {path}")
        else:
            print("[-] File not found or invalid command.")


def _print_entries(entries: Sequence[Tuple[str, ISO9660Entry]]) -> None:
    print(f"\n[+] Scanned Files on Image ({len(entries)} total):")
    print(f"{'Path':<45} | {'Type':<6} | {'LBA':<10} | {'Size (Bytes)'}")
    print("-" * 82)
    for path, entry in entries:
        kind = "DIR" if entry.is_dir else "FILE"
        print(
            f"{path:<45} | {kind:<6} | "
            f"0x{entry.lba:08X} | {entry.size}"
        )


def _report_summary(report: ExtractionReport) -> None:
    print(
        "[+] Extraction summary: "
        f"{report.extracted_count} files extracted, "
        f"{report.directory_count} directories, "
        f"{report.skipped_count} existing files skipped, "
        f"{report.error_count} errors."
    )
    if report.error_count:
        print("[!] Unsupported or failed extents:")
        for item in report.items:
            if item.status == "error":
                print(
                    f"    - {item.iso_path}: "
                    f"{item.error_type}: {item.error_message}"
                )


def _next_numbered_backup_path(
    output_path: os.PathLike[str] | str,
) -> str:
    """Return the first unused ``name(n).ext`` sibling for an output path."""

    path = os.path.abspath(os.fspath(output_path))
    if os.path.isdir(path):
        stem, extension = path, ""
    else:
        stem, extension = os.path.splitext(path)

    index = 1
    while True:
        candidate = f"{stem}({index}){extension}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _prompt_existing_output(
    output_path: str,
    *,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> str:
    """Ask how Mjolnir should handle an existing output path."""

    kind = "directory" if os.path.isdir(output_path) else "file"
    print_func(f"\n[!] Output {kind} already exists:")
    print_func(f"    {output_path}")
    print_func("")
    print_func("Choose an action:")
    print_func("    1. Cancel")
    print_func(f"    2. Auto-rename existing {kind}")
    print_func("    3. Overwrite")

    while True:
        choice = input_func("Select [1-3] (default 1): ").strip().lower()
        if choice in ("", "1", "cancel", "c"):
            return "cancel"
        if choice in ("2", "rename", "r"):
            return "rename"
        if choice in ("3", "overwrite", "o"):
            return "overwrite"
        print_func("[-] Invalid selection. Choose 1, 2, or 3.")


def _write_with_conflict_resolution(
    output_path: os.PathLike[str] | str,
    writer: Callable[[str, bool], str],
    *,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> OutputWriteResult:
    """Write a file with Mjolnir's Cancel/Rename/Overwrite policy."""

    path = os.path.abspath(os.fspath(output_path))
    if not os.path.exists(path):
        created = writer(path, False)
        return OutputWriteResult(created, "created")

    decision = _prompt_existing_output(
        path,
        input_func=input_func,
        print_func=print_func,
    )
    if decision == "cancel":
        return OutputWriteResult(path, "cancelled")
    if decision == "overwrite":
        created = writer(path, True)
        return OutputWriteResult(created, "overwritten")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix=".srk-mjolnir-output-",
        suffix=".tmp",
        dir=parent or None,
    )
    os.close(fd)

    backup_path: Optional[str] = None
    old_file_moved = False
    try:
        writer(temp_path, True)
        backup_path = _next_numbered_backup_path(path)
        os.rename(path, backup_path)
        old_file_moved = True

        try:
            os.replace(temp_path, path)
        except Exception:
            if not os.path.exists(path) and backup_path and os.path.exists(backup_path):
                os.rename(backup_path, path)
                old_file_moved = False
            raise

        return OutputWriteResult(path, "renamed_existing", backup_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if old_file_moved and not os.path.exists(path) and backup_path:
            if os.path.exists(backup_path):
                os.rename(backup_path, path)


def _write_directory_with_conflict_resolution(
    output_path: os.PathLike[str] | str,
    builder: Callable[[str], ExtractionReport],
    *,
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> Tuple[OutputWriteResult, Optional[ExtractionReport]]:
    """Build a directory with the same Cancel/Rename/Overwrite policy."""

    path = os.path.abspath(os.fspath(output_path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if not os.path.exists(path):
        report = builder(path)
        return OutputWriteResult(path, "created"), report

    decision = _prompt_existing_output(
        path,
        input_func=input_func,
        print_func=print_func,
    )
    if decision == "cancel":
        return OutputWriteResult(path, "cancelled"), None

    temp_path = tempfile.mkdtemp(
        prefix=".srk-mjolnir-directory-",
        dir=parent or None,
    )
    try:
        report = builder(temp_path)

        if decision == "rename":
            backup_path = _next_numbered_backup_path(path)
            old_output_moved = False
            os.rename(path, backup_path)
            old_output_moved = True
            try:
                os.rename(temp_path, path)
            except Exception:
                if not os.path.exists(path) and os.path.exists(backup_path):
                    os.rename(backup_path, path)
                    old_output_moved = False
                raise
            finally:
                if old_output_moved and not os.path.exists(path):
                    if os.path.exists(backup_path):
                        os.rename(backup_path, path)

            return (
                OutputWriteResult(path, "renamed_existing", backup_path),
                report,
            )

        old_backup = tempfile.mkdtemp(
            prefix=".srk-mjolnir-old-directory-",
            dir=parent or None,
        )
        os.rmdir(old_backup)
        old_output_moved = False
        os.rename(path, old_backup)
        old_output_moved = True
        try:
            os.rename(temp_path, path)
        except Exception:
            if not os.path.exists(path) and os.path.exists(old_backup):
                os.rename(old_backup, path)
                old_output_moved = False
            raise
        finally:
            if old_output_moved and not os.path.exists(path):
                if os.path.exists(old_backup):
                    os.rename(old_backup, path)

        if os.path.exists(old_backup):
            shutil.rmtree(old_backup, ignore_errors=True)

        return OutputWriteResult(path, "overwritten"), report
    finally:
        if os.path.exists(temp_path):
            shutil.rmtree(temp_path, ignore_errors=True)


def _write_filesystem_hex_blob(
    session: DiscSession,
    output_path: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
) -> str:
    """Write one text blob containing each readable ISO file as hex."""

    path = os.path.abspath(os.fspath(output_path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    mode = "w" if overwrite else "x"
    with open(path, mode, encoding="utf-8", newline="\n") as handle:
        for iso_path, entry in session.entries:
            if entry.is_dir:
                continue

            handle.write(
                f"=== FILE: {iso_path} "
                f"(LBA: 0x{entry.lba:08X}, Size: {entry.size}) ===\n"
            )
            try:
                data = session.reader.read_file(entry)
            except Exception as exc:
                handle.write(
                    f"=== SRK READ ERROR: {type(exc).__name__}: {exc} ===\n\n"
                )
                continue

            for line in iter_hexdump_lines(data):
                handle.write(line)
                handle.write("\n")
            handle.write("\n")

    return path


def _structured_output_root(workspace_root: str, base_name: str) -> str:
    return os.path.join(workspace_root, "extracted_output", base_name)


def _portable_zip_output_path(workspace_root: str, base_name: str) -> str:
    return os.path.join(
        workspace_root,
        "extracted_output",
        f"{base_name}-dump.zip",
    )


def _write_portable_zip(
    session: DiscSession,
    output_path: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
) -> Tuple[str, ExtractionReport]:
    """Build a portable ZIP completely before publishing it to ``output_path``."""

    path = os.path.abspath(os.fspath(output_path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")

    with tempfile.TemporaryDirectory(
        prefix=".srk-mjolnir-extract-",
        dir=parent or None,
    ) as temp_dir:
        report = session.extractor.extract_all(
            temp_dir,
            overwrite=False,
            continue_on_error=True,
        )

        fd, archive_stub = tempfile.mkstemp(
            prefix=".srk-mjolnir-archive-",
            dir=parent or None,
        )
        os.close(fd)
        os.remove(archive_stub)
        created_archive = ""
        try:
            created_archive = shutil.make_archive(
                archive_stub,
                "zip",
                temp_dir,
            )
            if os.path.exists(path):
                if not overwrite:
                    raise FileExistsError(f"Output already exists: {path}")
                os.replace(created_archive, path)
            else:
                os.rename(created_archive, path)
        finally:
            if created_archive and os.path.exists(created_archive):
                try:
                    os.remove(created_archive)
                except OSError:
                    pass

    return path, report


def _menu_option_lines(
    session: Optional[DiscSession],
    active_file: Optional[Tuple[str, ISO9660Entry]],
) -> List[str]:
    """Return menu labels previewing the outputs Mjolnir will write."""

    if session is None:
        file_hex = "<filename>.hex"
        image_hex = "<imagefilename>.hex"
        structured = "extracted_output/<image>/"
        portable = "extracted_output/<image>-dump.zip"
    else:
        file_hex = (
            f"{active_file[1].name}.hex"
            if active_file is not None
            else "<filename>.hex"
        )
        image_hex = f"{session.base_name}.hex"
        structured = f"extracted_output/{session.base_name}/"
        portable = f"extracted_output/{session.base_name}-dump.zip"

    return [
        "0. Select image",
        "1. Deselect image",
        "2. Scan image (list available files)",
        "3. Select target file",
        f"4. Dump active file to hex file ({file_hex})",
        f"5. Dump filesystem to one hex blob ({image_hex})",
        f"6. Structured image dump ({structured})",
        f"7. Portable structured dump ({portable})",
        "8. Exit",
    ]


def _print_output_write_result(result: OutputWriteResult) -> None:
    if result.action == "cancelled":
        print("[+] Cancelled. Existing output left unchanged.")
    elif result.action == "renamed_existing":
        print(f"[+] Preserved existing output as: {result.backup_path}")
    elif result.action == "overwritten":
        print(f"[!] Existing output overwritten: {result.output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-mjolnir",
        description="Interactive read-only disc explorer and hex research utility",
    )
    parser.add_argument(
        "source",
        nargs="?",
        help=(
            "Disc image/CUE to open immediately, or a directory to search. "
            "Defaults to the current working directory."
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help=(
            "Workspace root for generated HEX files and extracted_output/. "
            "Defaults to the current working directory."
        ),
    )
    return parser


def _display_candidate(path: str, search_root: str) -> str:
    try:
        return os.path.relpath(path, search_root)
    except ValueError:
        return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    workspace_root = os.path.abspath(os.fspath(args.output_dir))
    os.makedirs(workspace_root, exist_ok=True)

    try:
        search_root, session = _resolve_startup_source(args.source)
    except Exception as exc:
        print(f"[-] Unable to use input source: {type(exc).__name__}: {exc}")
        return 2

    active_file: Optional[Tuple[str, ISO9660Entry]] = None

    while True:
        active_display = (
            os.path.basename(session.source_path)
            if session is not None
            else "[ None Selected ]"
        )
        file_display = active_file[0] if active_file else "[ None Selected ]"

        print("\n" + "=" * 64)
        print("               SRK MJOLNIR DISC & HEX UTILITY")
        print("=" * 64)
        print(f"Active Image: {active_display}")
        print(f"Active File:  {file_display}")
        print("-" * 64)
        for menu_line in _menu_option_lines(session, active_file):
            print(menu_line)
        print("-" * 64)

        try:
            choice = input("Select an option [0-8]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[+] Exiting Mjolnir.")
            return 0

        if choice == "8":
            print("[+] Exiting Mjolnir.")
            return 0

        if choice == "0":
            candidates = discover_disc_candidates(search_root)
            if not candidates:
                print(
                    "[-] No supported disc images found beneath: "
                    f"{search_root}"
                )
                print(
                    "    Restart Mjolnir with an image file or search directory, "
                    "for example: srk-mjolnir /path/to/images"
                )
                continue

            print("\n[+] Available disc images:")
            for index, candidate in enumerate(candidates):
                print(
                    f"    [{index}] "
                    f"{_display_candidate(candidate, search_root)}"
                )

            selected = input(
                f"Select image index [0-{len(candidates) - 1}]: "
            ).strip()
            if not selected.isdigit():
                print("[-] Invalid selection.")
                continue

            index = int(selected)
            if not 0 <= index < len(candidates):
                print("[-] Selection out of range.")
                continue

            try:
                print("[+] Opening image read-only...")
                session = open_disc(candidates[index])
            except Exception as exc:
                print(f"[-] Failed to open image: {type(exc).__name__}: {exc}")
                session = None
                active_file = None
                continue

            active_file = None
            print(
                f"[+] Image opened: {os.path.basename(session.source_path)} "
                f"({len(session.entries)} indexed items)"
            )
            continue

        if choice == "1":
            session = None
            active_file = None
            print("[+] Image deselected.")
            continue

        if session is None:
            print("\n[-] No image selected. Choose option 0 first.")
            continue

        if choice == "2":
            _print_entries(session.entries)

        elif choice == "3":
            active_file = select_target_file(session.entries)

        elif choice == "4":
            if active_file is None:
                print("[-] No active file selected.")
                active_file = select_target_file(session.entries)
                if active_file is None:
                    continue

            iso_path, entry = active_file
            try:
                data = session.reader.read_file(entry)
                output = os.path.join(workspace_root, f"{entry.name}.hex")
                result = _write_with_conflict_resolution(
                    output,
                    lambda path, overwrite: write_hexdump(
                        data,
                        path,
                        overwrite=overwrite,
                    ),
                )
            except Exception as exc:
                print(f"[-] Hex dump failed: {type(exc).__name__}: {exc}")
            else:
                _print_output_write_result(result)
                if result.action != "cancelled":
                    print(f"[+] Dumped {iso_path} to {result.output_path}")

        elif choice == "5":
            output = os.path.join(workspace_root, f"{session.base_name}.hex")
            try:
                result = _write_with_conflict_resolution(
                    output,
                    lambda path, overwrite: _write_filesystem_hex_blob(
                        session,
                        path,
                        overwrite=overwrite,
                    ),
                )
            except Exception as exc:
                print(f"[-] Hex blob failed: {type(exc).__name__}: {exc}")
            else:
                _print_output_write_result(result)
                if result.action != "cancelled":
                    print(
                        f"[+] Complete hex blob saved to "
                        f"{result.output_path}"
                    )

        elif choice == "6":
            output_root = _structured_output_root(
                workspace_root,
                session.base_name,
            )
            try:
                result, report = _write_directory_with_conflict_resolution(
                    output_root,
                    lambda path: session.extractor.extract_all(
                        path,
                        overwrite=False,
                        continue_on_error=True,
                    ),
                )
            except Exception as exc:
                print(
                    f"[-] Structured extraction failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                _print_output_write_result(result)
                if result.action != "cancelled" and report is not None:
                    _report_summary(report)
                    print(f"[+] Structured dump created: {result.output_path}")

        elif choice == "7":
            output = _portable_zip_output_path(
                workspace_root,
                session.base_name,
            )
            report_holder: List[ExtractionReport] = []

            def write_zip(path: str, overwrite: bool) -> str:
                created, report = _write_portable_zip(
                    session,
                    path,
                    overwrite=overwrite,
                )
                report_holder.append(report)
                return created

            try:
                result = _write_with_conflict_resolution(output, write_zip)
            except Exception as exc:
                print(
                    f"[-] Portable dump failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                _print_output_write_result(result)
                if result.action != "cancelled":
                    if report_holder:
                        _report_summary(report_holder[-1])
                    print(
                        f"[+] Portable archive created: "
                        f"{result.output_path}"
                    )

        else:
            print("[-] Invalid choice. Please select between 0 and 8.")


if __name__ == "__main__":
    raise SystemExit(main())
