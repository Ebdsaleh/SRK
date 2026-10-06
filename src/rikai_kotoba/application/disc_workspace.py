"""Application-layer disc workspace built on SRK's generic read-only core."""

from __future__ import annotations

from dataclasses import dataclass
import os
import threading
from typing import Optional, Tuple

from rikai_kotoba.core.cue_disc import CueDisc
from rikai_kotoba.core.disc_image import DiscImage
from rikai_kotoba.core.disc_source import open_disc_source
from rikai_kotoba.core.iso9660 import ISO9660Reader


@dataclass(frozen=True)
class DiscEntrySnapshot:
    path: str
    name: str
    lba: int
    size: int
    is_dir: bool


@dataclass(frozen=True)
class DiscWorkspaceSnapshot:
    source_path: str
    source_kind: str
    base_name: str
    entries: Tuple[DiscEntrySnapshot, ...]

    @property
    def file_count(self) -> int:
        return sum(not entry.is_dir for entry in self.entries)

    @property
    def directory_count(self) -> int:
        return sum(entry.is_dir for entry in self.entries)


@dataclass
class _DiscSession:
    source: object
    reader: ISO9660Reader
    snapshot: DiscWorkspaceSnapshot


class DiscWorkspaceService:
    """Own the active logical disc independently of GUI presentation.

    The service performs no Dear PyGui work. It is safe to call ``open_source``
    from SRK's background worker service; the fully parsed session becomes
    visible atomically only after the open/ISO walk succeeds.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: Optional[_DiscSession] = None

    @staticmethod
    def _source_kind(source: object) -> str:
        if isinstance(source, CueDisc):
            return f"CUE multi-track ({len(source.tracks)} track(s))"
        if isinstance(source, DiscImage):
            return source.geometry.name
        return type(source).__name__

    def open_source(self, path: os.PathLike[str] | str) -> DiscWorkspaceSnapshot:
        source_path = os.path.abspath(os.fspath(path))
        source = open_disc_source(source_path)
        reader = ISO9660Reader(source)
        entries = tuple(
            DiscEntrySnapshot(
                path=iso_path,
                name=entry.name,
                lba=entry.lba,
                size=entry.size,
                is_dir=entry.is_dir,
            )
            for iso_path, entry in reader.walk()
        )
        snapshot = DiscWorkspaceSnapshot(
            source_path=source_path,
            source_kind=self._source_kind(source),
            base_name=os.path.splitext(os.path.basename(source_path))[0],
            entries=entries,
        )
        with self._lock:
            self._session = _DiscSession(source, reader, snapshot)
        return snapshot

    def close_source(self) -> None:
        with self._lock:
            self._session = None

    def snapshot(self) -> DiscWorkspaceSnapshot | None:
        with self._lock:
            return self._session.snapshot if self._session is not None else None

    def read_file(self, iso_path: str) -> bytes:
        with self._lock:
            session = self._session
        if session is None:
            raise RuntimeError("no disc source is open")
        return session.reader.read_file(iso_path)
