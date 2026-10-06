"""Mjolnir: interactive SRK disc/hex research utility.

This is the cleaned successor to the original ``hexdump.py`` experiment.  It
keeps the useful interactive workflow while delegating disc geometry, CUE
mapping, ISO-9660 parsing, and safe extraction to SRK core modules.

Run from the project root with:

    set PYTHONPATH=src
    python -m rikai_kotoba.tools.mjolnir
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import tempfile
from typing import List, Optional, Sequence, Tuple

from rikai_kotoba.core.cue_disc import CueDisc, parse_cue
from rikai_kotoba.core.disc_image import DiscImage
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


def _canonical(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def discover_disc_candidates(
    iso_dir: os.PathLike[str] | str,
) -> List[str]:
    """Return CUE sheets plus standalone images not already owned by a CUE.

    When both ``game.cue`` and its ``Track 1.bin`` / ``Track 2.bin`` files are
    present, the CUE is the meaningful whole-disc object and the referenced
    track files are suppressed from the selection list.
    """

    root = os.path.abspath(os.fspath(iso_dir))
    if not os.path.isdir(root):
        return []

    cues: List[str] = []
    standalones: List[str] = []
    for current_root, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(current_root, name)
            suffix = os.path.splitext(name)[1].lower()
            if suffix == ".cue":
                cues.append(path)
            elif suffix in (".bin", ".img", ".iso", ".raw"):
                standalones.append(path)

    cues.sort(key=str.casefold)
    standalones.sort(key=str.casefold)

    referenced: set[str] = set()
    for cue in cues:
        try:
            tracks = parse_cue(cue)
        except Exception:
            continue
        cue_dir = os.path.dirname(cue)
        for track in tracks:
            target = track.file_name
            if not os.path.isabs(target):
                target = os.path.join(cue_dir, target)
            referenced.add(_canonical(target))

    return cues + [
        path for path in standalones if _canonical(path) not in referenced
    ]


def open_disc(path: os.PathLike[str] | str) -> DiscSession:
    """Open a CUE-backed or standalone data image as a read-only SRK session."""

    source_path = os.path.abspath(os.fspath(path))
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Disc image not found: {source_path}")

    if os.path.splitext(source_path)[1].lower() == ".cue":
        source = CueDisc(source_path)
    else:
        source = DiscImage(source_path)

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


def _write_filesystem_hex_blob(
    session: DiscSession,
    output_path: os.PathLike[str] | str,
) -> str:
    """Write one text blob containing each readable ISO file as hex.

    Files whose extents cannot be represented as ISO user data (for example an
    audio-track pseudo-file) are recorded as explicit diagnostics instead of
    being written as empty data.
    """

    path = os.path.abspath(os.fspath(output_path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "x", encoding="utf-8", newline="\n") as handle:
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


def _structured_output_root(project_root: str, base_name: str) -> str:
    return os.path.join(project_root, "extracted_output", base_name)


def _create_portable_zip(
    session: DiscSession,
    project_root: str,
) -> Tuple[str, ExtractionReport]:
    output_dir = os.path.join(project_root, "extracted_output")
    os.makedirs(output_dir, exist_ok=True)

    zip_path = os.path.join(output_dir, f"{session.base_name}-dump.zip")
    if os.path.exists(zip_path):
        raise FileExistsError(f"Output already exists: {zip_path}")

    with tempfile.TemporaryDirectory(
        prefix=".srk-mjolnir-",
        dir=output_dir,
    ) as temp_dir:
        report = session.extractor.extract_all(
            temp_dir,
            overwrite=False,
            continue_on_error=True,
        )
        archive_base = os.path.splitext(zip_path)[0]
        created = shutil.make_archive(archive_base, "zip", temp_dir)

    return created, report


def main() -> None:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    iso_dir = os.path.join(project_root, "iso")

    session: Optional[DiscSession] = None
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
        print("0. Select image")
        print("1. Deselect image")
        print("2. Scan image (list available files)")
        print("3. Select target file")
        print("4. Dump active file to hex file (<filename>.hex)")
        print("5. Dump filesystem to one hex blob (<imagefilename>.hex)")
        print("6. Structured image dump (extracted_output/<image>/)")
        print("7. Portable structured dump (extracted_output/<image>-dump.zip)")
        print("8. Exit")
        print("-" * 64)

        choice = input("Select an option [0-8]: ").strip()

        if choice == "8":
            print("[+] Exiting Mjolnir.")
            break

        if choice == "0":
            candidates = discover_disc_candidates(iso_dir)
            if not candidates:
                print(f"[-] No supported disc images found beneath: {iso_dir}")
                continue

            print("\n[+] Available disc images:")
            for index, candidate in enumerate(candidates):
                print(
                    f"    [{index}] "
                    f"{os.path.relpath(candidate, project_root)}"
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
                output = os.path.join(project_root, f"{entry.name}.hex")
                created = write_hexdump(data, output, overwrite=False)
            except Exception as exc:
                print(f"[-] Hex dump failed: {type(exc).__name__}: {exc}")
            else:
                print(f"[+] Dumped {iso_path} to {created}")

        elif choice == "5":
            output = os.path.join(
                project_root,
                f"{session.base_name}.hex",
            )
            print(f"[+] Generating filesystem hex blob: {output}")
            try:
                created = _write_filesystem_hex_blob(session, output)
            except Exception as exc:
                print(f"[-] Hex blob failed: {type(exc).__name__}: {exc}")
            else:
                print(f"[+] Complete hex blob saved to {created}")

        elif choice == "6":
            output_root = _structured_output_root(
                project_root,
                session.base_name,
            )
            print(f"[+] Extracting safely into: {output_root}")
            try:
                report = session.extractor.extract_all(
                    output_root,
                    overwrite=False,
                    continue_on_error=True,
                )
            except Exception as exc:
                print(
                    f"[-] Structured extraction failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                _report_summary(report)

        elif choice == "7":
            print("[+] Building portable structured dump...")
            try:
                archive, report = _create_portable_zip(
                    session,
                    project_root,
                )
            except Exception as exc:
                print(
                    f"[-] Portable dump failed: "
                    f"{type(exc).__name__}: {exc}"
                )
            else:
                _report_summary(report)
                print(f"[+] Portable archive created: {archive}")

        else:
            print("[-] Invalid choice. Please select between 0 and 8.")


if __name__ == "__main__":
    main()
