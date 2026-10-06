"""Generic read-only ISO-9660 filesystem access for SRK.

``ISO9660Reader`` operates on a logical-sector source rather than directly on a
file.  A source may be a single-track ``DiscImage``, a multi-track ``CueDisc``,
or any future object that exposes compatible 2048-byte user-sector reads.

This module contains no platform- or game-specific knowledge and never writes
to its source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Set, Tuple, Union


ISO_SECTOR_SIZE = 2048
PVD_LBA = 16
PVD_IDENTIFIER = b"CD001"


class ISO9660Error(Exception):
    """Base error for ISO-9660 filesystem operations."""


class InvalidISO9660Error(ISO9660Error):
    """Raised when the logical source does not contain a valid ISO-9660 PVD."""


class ISO9660PathError(ISO9660Error):
    """Raised when an ISO-9660 path cannot be resolved safely."""


@dataclass(frozen=True)
class ISO9660Entry:
    """One ISO-9660 directory entry."""

    name: str
    raw_name: str
    lba: int
    size: int
    is_dir: bool

    @property
    def sector_count(self) -> int:
        if self.size == 0:
            return 0
        return (self.size + ISO_SECTOR_SIZE - 1) // ISO_SECTOR_SIZE


def _clean_identifier(identifier: bytes) -> Tuple[str, str]:
    """Decode an ISO identifier and remove only the standard ``;version`` tail."""

    raw_name = identifier.decode("ascii", errors="replace")
    if raw_name == "\x00":
        return ".", raw_name
    if raw_name == "\x01":
        return "..", raw_name

    name = raw_name
    if ";" in name:
        stem, version = name.rsplit(";", 1)
        if version.isdigit():
            name = stem
    return name, raw_name


class ISO9660Reader:
    """Read-only ISO-9660 reader backed by a logical-sector source.

    The source must provide either ``read_user_sector(lba)`` (preferred for
    CUE-backed discs) or ``read_lba(lba)`` (used by ``DiscImage``). Optional
    ``read_user_extent``/``read_file_extent`` methods are used when available.
    """

    def __init__(self, source: object) -> None:
        self.source = source
        self.root = self._parse_pvd()

    def _read_sector(self, lba: int) -> bytes:
        reader = getattr(self.source, "read_user_sector", None)
        if reader is None:
            reader = getattr(self.source, "read_lba", None)
        if reader is None:
            raise TypeError(
                "ISO9660Reader source must provide read_user_sector(lba) "
                "or read_lba(lba)"
            )

        data = reader(lba)
        if len(data) != ISO_SECTOR_SIZE:
            raise ISO9660Error(
                f"Logical sector {lba} returned {len(data)} bytes; "
                f"expected {ISO_SECTOR_SIZE}"
            )
        return data

    def _read_extent(self, start_lba: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must be non-negative")
        if size == 0:
            return b""

        reader = getattr(self.source, "read_user_extent", None)
        if reader is None:
            reader = getattr(self.source, "read_file_extent", None)
        if reader is not None:
            data = reader(start_lba, size)
            if len(data) != size:
                raise ISO9660Error(
                    f"Extent at LBA {start_lba} returned {len(data)} bytes; "
                    f"expected {size}"
                )
            return data

        sectors = (size + ISO_SECTOR_SIZE - 1) // ISO_SECTOR_SIZE
        result = bytearray()
        for lba in range(start_lba, start_lba + sectors):
            result.extend(self._read_sector(lba))
        return bytes(result[:size])

    @staticmethod
    def _parse_record(record: bytes) -> ISO9660Entry:
        if len(record) < 34:
            raise InvalidISO9660Error(
                f"ISO directory record is too short: {len(record)} bytes"
            )

        record_len = record[0]
        if record_len == 0 or record_len > len(record):
            raise InvalidISO9660Error(
                f"Invalid ISO directory record length: {record_len}"
            )

        extent_lba = int.from_bytes(record[2:6], "little")
        data_length = int.from_bytes(record[10:14], "little")
        flags = record[25]
        name_len = record[32]

        if 33 + name_len > record_len:
            raise InvalidISO9660Error(
                "ISO directory identifier exceeds its record boundary"
            )

        name, raw_name = _clean_identifier(record[33 : 33 + name_len])
        return ISO9660Entry(
            name=name,
            raw_name=raw_name,
            lba=extent_lba,
            size=data_length,
            is_dir=bool(flags & 0x02),
        )

    def _parse_pvd(self) -> ISO9660Entry:
        pvd = self._read_sector(PVD_LBA)
        if pvd[0] != 0x01 or pvd[1:6] != PVD_IDENTIFIER or pvd[6] != 0x01:
            raise InvalidISO9660Error(
                "Invalid ISO-9660 Primary Volume Descriptor at LBA 16"
            )

        record_len = pvd[156]
        if record_len == 0:
            raise InvalidISO9660Error("ISO-9660 PVD has no root directory record")
        root = self._parse_record(pvd[156 : 156 + record_len])
        if not root.is_dir:
            raise InvalidISO9660Error("ISO-9660 root record is not a directory")
        return root

    def _directory_entries(self, directory: ISO9660Entry) -> List[ISO9660Entry]:
        if not directory.is_dir:
            raise ISO9660PathError(f"Not a directory: {directory.name}")

        data = self._read_extent(directory.lba, directory.size)
        entries: List[ISO9660Entry] = []
        offset = 0

        while offset < len(data):
            record_len = data[offset]
            if record_len == 0:
                offset = ((offset // ISO_SECTOR_SIZE) + 1) * ISO_SECTOR_SIZE
                continue

            sector_offset = offset % ISO_SECTOR_SIZE
            if sector_offset + record_len > ISO_SECTOR_SIZE:
                raise InvalidISO9660Error(
                    "ISO directory record crosses a logical-sector boundary"
                )
            if offset + record_len > len(data):
                raise InvalidISO9660Error(
                    "ISO directory record extends past directory data"
                )

            entry = self._parse_record(data[offset : offset + record_len])
            if entry.name not in (".", ".."):
                entries.append(entry)
            offset += record_len

        return entries

    def list_root_directory(self) -> List[ISO9660Entry]:
        """Return root directory entries, excluding ``.`` and ``..``."""

        return self._directory_entries(self.root)

    def list_directory(
        self, directory: Union[str, ISO9660Entry] = "/"
    ) -> List[ISO9660Entry]:
        """List an ISO directory selected by path or entry."""

        entry = directory if isinstance(directory, ISO9660Entry) else self.get_entry(directory)
        return self._directory_entries(entry)

    def get_entry(self, path: str) -> ISO9660Entry:
        """Resolve a slash-separated ISO path case-insensitively."""

        normalized = path.replace("\\", "/").strip()
        if normalized in ("", "/"):
            return self.root

        parts = [part for part in normalized.strip("/").split("/") if part]
        current = self.root

        for index, part in enumerate(parts):
            if part in (".", ".."):
                raise ISO9660PathError(
                    "Relative '.' and '..' components are not accepted"
                )

            matches = [
                entry
                for entry in self._directory_entries(current)
                if entry.name.casefold() == part.casefold()
                or entry.raw_name.casefold() == part.casefold()
            ]
            if not matches:
                raise ISO9660PathError(f"ISO path not found: {path}")
            if len(matches) > 1:
                raise ISO9660PathError(f"Ambiguous ISO path component: {part}")

            current = matches[0]
            if index < len(parts) - 1 and not current.is_dir:
                raise ISO9660PathError(
                    f"ISO path component is not a directory: {part}"
                )

        return current

    def read_file(self, file: Union[str, ISO9660Entry]) -> bytes:
        """Read one file extent from the logical source.

        Source-level errors are intentionally propagated so callers receive a
        precise diagnostic instead of partial data.
        """

        entry = self.get_entry(file) if isinstance(file, str) else file
        if entry.is_dir:
            raise ISO9660PathError(f"Cannot read a directory as a file: {entry.name}")
        return self._read_extent(entry.lba, entry.size)

    def walk(self) -> Iterator[Tuple[str, ISO9660Entry]]:
        """Yield ``(path, entry)`` for the reachable filesystem tree."""

        visited: Set[Tuple[int, int]] = set()

        def recurse(
            directory: ISO9660Entry, prefix: str
        ) -> Iterator[Tuple[str, ISO9660Entry]]:
            key = (directory.lba, directory.size)
            if key in visited:
                return
            visited.add(key)

            for entry in self._directory_entries(directory):
                path = f"{prefix}/{entry.name}" if prefix else f"/{entry.name}"
                yield path, entry
                if entry.is_dir:
                    yield from recurse(entry, path)

        yield from recurse(self.root, "")
