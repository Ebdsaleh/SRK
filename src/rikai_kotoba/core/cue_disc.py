"""Read-only CUE-sheet backed logical-disc access for SRK.

``CueDisc`` maps the physical files referenced by a CUE sheet into one
continuous logical-sector address space.  It deliberately performs no writes
and contains no game-specific knowledge.

This is the layer used when a title spans multiple track files.  A caller can
locate any logical block address (LBA), read raw sectors across file boundaries,
and read 2048-byte user sectors from supported data tracks.  Audio sectors are
reported explicitly instead of being silently treated as ISO data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional, Tuple


class CueDiscError(Exception):
    """Base error for CUE-backed logical-disc operations."""


class CueParseError(CueDiscError):
    """Raised when a CUE sheet is malformed or incomplete."""


class UnsupportedTrackModeError(CueDiscError):
    """Raised when SRK does not yet understand a track's sector layout."""


class NonDataTrackError(CueDiscError):
    """Raised when user-data access is requested from a non-data track."""


@dataclass(frozen=True)
class TrackMode:
    name: str
    sector_size: int
    user_data_offset: Optional[int]
    user_data_size: Optional[int]

    @property
    def is_data(self) -> bool:
        return self.user_data_offset is not None and self.user_data_size is not None


TRACK_MODES: Dict[str, TrackMode] = {
    "MODE1/2048": TrackMode("MODE1/2048", 2048, 0, 2048),
    "MODE1/2352": TrackMode("MODE1/2352", 2352, 16, 2048),
    "MODE2/2352": TrackMode("MODE2/2352", 2352, 24, 2048),
    "AUDIO": TrackMode("AUDIO", 2352, None, None),
}


@dataclass
class CueTrack:
    number: int
    mode_name: str
    file_name: str
    file_type: str
    indices: Dict[int, int] = field(default_factory=dict)

    @property
    def mode(self) -> TrackMode:
        try:
            return TRACK_MODES[self.mode_name.upper()]
        except KeyError as exc:
            raise UnsupportedTrackModeError(
                f"Unsupported CUE track mode: {self.mode_name}"
            ) from exc

    @property
    def physical_start_sector(self) -> int:
        """First physical sector belonging to this track inside its file.

        INDEX 00 represents a stored pregap when present.  Otherwise INDEX 01
        is the first known sector.  Missing INDEX entries are rejected because
        silently assuming zero would make logical-LBA mapping unsafe.
        """

        if 0 in self.indices:
            return self.indices[0]
        if 1 in self.indices:
            return self.indices[1]
        raise CueParseError(f"TRACK {self.number:02d} has no INDEX 00/01 entry")

    @property
    def program_start_sector(self) -> int:
        if 1 in self.indices:
            return self.indices[1]
        return self.physical_start_sector


@dataclass(frozen=True)
class CueFileSegment:
    path: str
    file_type: str
    sector_size: int
    base_lba: int
    sector_count: int

    @property
    def end_lba(self) -> int:
        return self.base_lba + self.sector_count


@dataclass(frozen=True)
class CueSectorLocation:
    lba: int
    file_path: str
    file_sector: int
    track_number: int
    track_mode: str
    raw_sector_size: int


_FILE_RE = re.compile(r'^FILE\s+(?:"([^"]+)"|(\S+))\s+(\S+)', re.IGNORECASE)
_TRACK_RE = re.compile(r'^TRACK\s+(\d+)\s+(\S+)', re.IGNORECASE)
_INDEX_RE = re.compile(r'^INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)', re.IGNORECASE)


def _msf_to_sectors(minutes: int, seconds: int, frames: int) -> int:
    if minutes < 0 or seconds < 0 or frames < 0:
        raise CueParseError("Negative CUE time is invalid")
    if seconds >= 60:
        raise CueParseError(f"Invalid CUE seconds value: {seconds}")
    if frames >= 75:
        raise CueParseError(f"Invalid CUE frame value: {frames}")
    return ((minutes * 60) + seconds) * 75 + frames


def parse_cue(cue_path: os.PathLike[str] | str) -> List[CueTrack]:
    """Parse FILE/TRACK/INDEX records from a CUE sheet.

    Paths are retained exactly as named in the CUE; ``CueDisc`` resolves them
    relative to the CUE sheet directory.
    """

    path = os.path.abspath(os.fspath(cue_path))
    if not os.path.isfile(path):
        raise FileNotFoundError(f"CUE sheet not found: {path}")

    tracks: List[CueTrack] = []
    current_file: Optional[Tuple[str, str]] = None
    current_track: Optional[CueTrack] = None

    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.upper().startswith("REM "):
                continue

            file_match = _FILE_RE.match(line)
            if file_match:
                file_name = file_match.group(1) or file_match.group(2)
                current_file = (file_name, file_match.group(3).upper())
                current_track = None
                continue

            track_match = _TRACK_RE.match(line)
            if track_match:
                if current_file is None:
                    raise CueParseError(
                        f"TRACK before FILE at line {line_number}: {line}"
                    )
                current_track = CueTrack(
                    number=int(track_match.group(1)),
                    mode_name=track_match.group(2).upper(),
                    file_name=current_file[0],
                    file_type=current_file[1],
                )
                tracks.append(current_track)
                continue

            index_match = _INDEX_RE.match(line)
            if index_match:
                if current_track is None:
                    raise CueParseError(
                        f"INDEX before TRACK at line {line_number}: {line}"
                    )
                index_number = int(index_match.group(1))
                current_track.indices[index_number] = _msf_to_sectors(
                    int(index_match.group(2)),
                    int(index_match.group(3)),
                    int(index_match.group(4)),
                )
                continue

    if not tracks:
        raise CueParseError(f"No tracks found in CUE sheet: {path}")

    seen_numbers = set()
    for track in tracks:
        if track.number in seen_numbers:
            raise CueParseError(f"Duplicate TRACK number: {track.number:02d}")
        seen_numbers.add(track.number)
        _ = track.mode
        _ = track.physical_start_sector

    return tracks


class CueDisc:
    """Read-only logical disc assembled from one or more CUE track files."""

    def __init__(self, cue_path: os.PathLike[str] | str) -> None:
        self.cue_path = os.path.abspath(os.fspath(cue_path))
        self.cue_dir = os.path.dirname(self.cue_path)
        self.tracks = parse_cue(self.cue_path)
        self.files = self._build_file_segments()
        self.total_sectors = sum(segment.sector_count for segment in self.files)
        self._track_starts = self._build_track_starts()

    def _resolve_file(self, file_name: str) -> str:
        candidate = file_name
        if not os.path.isabs(candidate):
            candidate = os.path.join(self.cue_dir, candidate)
        candidate = os.path.abspath(candidate)
        if not os.path.isfile(candidate):
            raise FileNotFoundError(f"CUE track file not found: {candidate}")
        return candidate

    def _build_file_segments(self) -> List[CueFileSegment]:
        """Map each physical CUE file once into contiguous logical LBA space."""

        ordered_names: List[str] = []
        tracks_by_file: Dict[str, List[CueTrack]] = {}

        for track in self.tracks:
            key = os.path.normcase(os.path.normpath(track.file_name))
            if key not in tracks_by_file:
                ordered_names.append(key)
                tracks_by_file[key] = []
            tracks_by_file[key].append(track)

        segments: List[CueFileSegment] = []
        base_lba = 0

        for key in ordered_names:
            file_tracks = tracks_by_file[key]
            path = self._resolve_file(file_tracks[0].file_name)
            sector_sizes = {track.mode.sector_size for track in file_tracks}
            if len(sector_sizes) != 1:
                raise UnsupportedTrackModeError(
                    "Tracks sharing one physical CUE file use different sector "
                    f"sizes, which is not yet supported safely: {path}"
                )
            sector_size = sector_sizes.pop()
            size = os.path.getsize(path)
            if size % sector_size != 0:
                raise CueDiscError(
                    f"Track file size is not divisible by its sector size "
                    f"({sector_size}): {path} ({size} bytes)"
                )
            sector_count = size // sector_size
            segments.append(
                CueFileSegment(
                    path=path,
                    file_type=file_tracks[0].file_type,
                    sector_size=sector_size,
                    base_lba=base_lba,
                    sector_count=sector_count,
                )
            )
            base_lba += sector_count

        return segments

    def _segment_for_track(self, track: CueTrack) -> CueFileSegment:
        target = self._resolve_file(track.file_name)
        for segment in self.files:
            if os.path.normcase(segment.path) == os.path.normcase(target):
                return segment
        raise CueDiscError(f"Internal error: no segment for TRACK {track.number:02d}")

    def _build_track_starts(self) -> List[Tuple[int, CueTrack]]:
        starts: List[Tuple[int, CueTrack]] = []
        for track in self.tracks:
            segment = self._segment_for_track(track)
            start = segment.base_lba + track.physical_start_sector
            if start >= segment.end_lba:
                raise CueParseError(
                    f"TRACK {track.number:02d} starts outside its file: "
                    f"sector {track.physical_start_sector}"
                )
            starts.append((start, track))
        starts.sort(key=lambda item: item[0])
        return starts

    def _find_file_segment(self, lba: int) -> CueFileSegment:
        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(
                f"LBA {lba} out of bounds (total sectors: {self.total_sectors})"
            )
        for segment in self.files:
            if segment.base_lba <= lba < segment.end_lba:
                return segment
        raise CueDiscError(f"Internal error: LBA {lba} has no file segment")

    def _find_track(self, lba: int) -> CueTrack:
        selected: Optional[CueTrack] = None
        for start, track in self._track_starts:
            if start > lba:
                break
            selected = track
        if selected is None:
            raise CueDiscError(f"LBA {lba} precedes the first CUE track")
        return selected

    def locate_lba(self, lba: int) -> CueSectorLocation:
        """Describe the physical file/sector that backs a logical LBA."""

        segment = self._find_file_segment(lba)
        track = self._find_track(lba)
        return CueSectorLocation(
            lba=lba,
            file_path=segment.path,
            file_sector=lba - segment.base_lba,
            track_number=track.number,
            track_mode=track.mode.name,
            raw_sector_size=segment.sector_size,
        )

    def read_sector(self, lba: int) -> bytes:
        """Read one physical sector from logical disc space."""

        location = self.locate_lba(lba)
        offset = location.file_sector * location.raw_sector_size
        with open(location.file_path, "rb") as handle:
            handle.seek(offset)
            data = handle.read(location.raw_sector_size)
        if len(data) != location.raw_sector_size:
            raise CueDiscError(
                f"Short sector read at LBA {lba}: expected "
                f"{location.raw_sector_size}, got {len(data)}"
            )
        return data

    def read_user_sector(self, lba: int) -> bytes:
        """Read the 2048-byte user-data region from a supported data track."""

        location = self.locate_lba(lba)
        track = self._find_track(lba)
        mode = track.mode
        if not mode.is_data:
            raise NonDataTrackError(
                f"LBA {lba} belongs to TRACK {track.number:02d} "
                f"({mode.name}), which has no ISO user-data payload"
            )

        raw = self.read_sector(lba)
        assert mode.user_data_offset is not None
        assert mode.user_data_size is not None
        end = mode.user_data_offset + mode.user_data_size
        if end > len(raw):
            raise CueDiscError(
                f"Track mode {mode.name} expects {end} bytes but sector contains "
                f"only {len(raw)}"
            )
        return raw[mode.user_data_offset:end]

    def read_user_extent(self, start_lba: int, size: int) -> bytes:
        """Read an ISO-style file extent, including across CUE file boundaries.

        Crossing into an audio track raises ``NonDataTrackError`` instead of
        returning truncated data.  This makes cross-track pseudo-files visible
        to callers rather than silently producing empty/partial output.
        """

        if size < 0:
            raise ValueError("size must be non-negative")
        if size == 0:
            return b""

        sectors = (size + 2047) // 2048
        result = bytearray()
        for lba in range(start_lba, start_lba + sectors):
            result.extend(self.read_user_sector(lba))
        return bytes(result[:size])
