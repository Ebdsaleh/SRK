"""Exact binary correlation primitives for runtime provenance research.

The first correlator intentionally proves only byte-for-byte evidence. It scans
source files in bounded chunks, searches those chunks inside a captured memory
dump, and coalesces adjacent matches into longer provenance runs. It does not
claim to detect compression, relocation fixups, decoding, or transformed data;
those require separate evidence and future analyzers.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Iterable


_ADDRESS_SPACE_SIZE = 1 << 32


@dataclass(frozen=True)
class CorrelationMatch:
    """One exact source chunk found at one memory-dump offset."""

    source_offset: int
    memory_offset: int
    memory_address: int
    length: int

    @property
    def displacement(self) -> int:
        """Dump-relative displacement useful when grouping contiguous runs."""
        return self.memory_offset - self.source_offset


@dataclass(frozen=True)
class CorrelationRun:
    """Adjacent exact chunk matches sharing one source-to-memory displacement."""

    source_offset: int
    memory_offset: int
    memory_address: int
    length: int
    chunk_count: int

    @property
    def source_end_exclusive(self) -> int:
        return self.source_offset + self.length

    @property
    def memory_end_address_exclusive(self) -> int:
        return self.memory_address + self.length


@dataclass(frozen=True)
class CorrelationReport:
    """Deterministic summary of one exact file-to-memory comparison."""

    source_path: str
    memory_dump_path: str
    source_size: int
    memory_dump_size: int
    memory_base_address: int
    source_sha256: str
    memory_dump_sha256: str
    chunk_size: int
    minimum_chunk_size: int
    scanned_chunks: int
    matched_chunks: int
    ambiguous_chunks: int
    runs: tuple[CorrelationRun, ...]

    @property
    def longest_run(self) -> CorrelationRun | None:
        if not self.runs:
            return None
        return max(self.runs, key=lambda run: (run.length, run.chunk_count))


@dataclass(frozen=True)
class _ChunkMatchSet:
    source_offset: int
    length: int
    memory_offsets: tuple[int, ...]
    ambiguous: bool = False


def _positive_int(value: object, *, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer") from exc
    if resolved <= 0:
        raise ValueError(f"{name} must be positive")
    return resolved


def _address(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("memory_base_address must be an integer")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("memory_base_address must be an integer") from exc
    if resolved < 0 or resolved >= _ADDRESS_SPACE_SIZE:
        raise ValueError("memory_base_address must fit in the 32-bit Saturn address space")
    return resolved


def _find_occurrences(
    haystack: bytes,
    needle: bytes,
    *,
    maximum_occurrences: int,
) -> tuple[tuple[int, ...], bool]:
    """Return exact occurrences, suppressing chunks that are too ambiguous."""

    offsets: list[int] = []
    start = 0
    while True:
        found = haystack.find(needle, start)
        if found < 0:
            return tuple(offsets), False
        offsets.append(found)
        if len(offsets) > maximum_occurrences:
            return (), True
        start = found + 1


def _coalesce(matches: Iterable[CorrelationMatch]) -> tuple[CorrelationRun, ...]:
    grouped: dict[int, list[CorrelationMatch]] = {}
    for match in matches:
        grouped.setdefault(match.displacement, []).append(match)

    runs: list[CorrelationRun] = []
    for displacement in sorted(grouped):
        ordered = sorted(grouped[displacement], key=lambda match: match.source_offset)
        current: CorrelationRun | None = None
        for match in ordered:
            if current is None:
                current = CorrelationRun(
                    source_offset=match.source_offset,
                    memory_offset=match.memory_offset,
                    memory_address=match.memory_address,
                    length=match.length,
                    chunk_count=1,
                )
                continue

            adjacent_source = match.source_offset == current.source_offset + current.length
            adjacent_memory = match.memory_offset == current.memory_offset + current.length
            if adjacent_source and adjacent_memory:
                current = CorrelationRun(
                    source_offset=current.source_offset,
                    memory_offset=current.memory_offset,
                    memory_address=current.memory_address,
                    length=current.length + match.length,
                    chunk_count=current.chunk_count + 1,
                )
            else:
                runs.append(current)
                current = CorrelationRun(
                    source_offset=match.source_offset,
                    memory_offset=match.memory_offset,
                    memory_address=match.memory_address,
                    length=match.length,
                    chunk_count=1,
                )
        if current is not None:
            runs.append(current)

    return tuple(sorted(runs, key=lambda run: (run.source_offset, run.memory_offset)))


def correlate_file_to_memory_dump(
    source_path: os.PathLike[str] | str,
    memory_dump_path: os.PathLike[str] | str,
    *,
    memory_base_address: int,
    chunk_size: int = 4096,
    minimum_chunk_size: int = 64,
    maximum_occurrences_per_chunk: int = 8,
) -> CorrelationReport:
    """Find exact source-file regions present in one captured memory dump.

    The memory dump is loaded once because Saturn capture regions are small
    compared with optical-disc files. The source is streamed one chunk at a
    time, so a large extracted file does not need to be held wholly in memory.
    Chunks that occur more than ``maximum_occurrences_per_chunk`` times are
    treated as ambiguous and omitted from provenance runs rather than flooding
    the report with low-value repeated patterns such as zero-filled pages.
    """

    source = Path(source_path)
    memory_path = Path(memory_dump_path)
    resolved_chunk_size = _positive_int(chunk_size, name="chunk_size")
    resolved_minimum = _positive_int(minimum_chunk_size, name="minimum_chunk_size")
    resolved_max_occurrences = _positive_int(
        maximum_occurrences_per_chunk,
        name="maximum_occurrences_per_chunk",
    )
    if resolved_minimum > resolved_chunk_size:
        raise ValueError("minimum_chunk_size must not exceed chunk_size")

    base_address = _address(memory_base_address)
    memory = memory_path.read_bytes()
    if base_address + len(memory) > _ADDRESS_SPACE_SIZE:
        raise ValueError("memory dump extends past the 32-bit Saturn address space")

    memory_hash = hashlib.sha256(memory).hexdigest()
    source_hash = hashlib.sha256()
    source_size = 0
    scanned_chunks = 0
    matched_chunks = 0
    ambiguous_chunks = 0
    chunk_match_sets: list[_ChunkMatchSet] = []

    with source.open("rb") as stream:
        source_offset = 0
        while True:
            chunk = stream.read(resolved_chunk_size)
            if not chunk:
                break
            source_hash.update(chunk)
            source_size += len(chunk)

            if len(chunk) >= resolved_minimum:
                scanned_chunks += 1
                offsets, ambiguous = _find_occurrences(
                    memory,
                    chunk,
                    maximum_occurrences=resolved_max_occurrences,
                )
                if ambiguous:
                    ambiguous_chunks += 1
                elif offsets:
                    matched_chunks += 1
                    chunk_match_sets.append(
                        _ChunkMatchSet(
                            source_offset=source_offset,
                            length=len(chunk),
                            memory_offsets=offsets,
                        )
                    )
            source_offset += len(chunk)

    matches = tuple(
        CorrelationMatch(
            source_offset=chunk_set.source_offset,
            memory_offset=memory_offset,
            memory_address=base_address + memory_offset,
            length=chunk_set.length,
        )
        for chunk_set in chunk_match_sets
        for memory_offset in chunk_set.memory_offsets
    )

    return CorrelationReport(
        source_path=str(source.resolve()),
        memory_dump_path=str(memory_path.resolve()),
        source_size=source_size,
        memory_dump_size=len(memory),
        memory_base_address=base_address,
        source_sha256=source_hash.hexdigest(),
        memory_dump_sha256=memory_hash,
        chunk_size=resolved_chunk_size,
        minimum_chunk_size=resolved_minimum,
        scanned_chunks=scanned_chunks,
        matched_chunks=matched_chunks,
        ambiguous_chunks=ambiguous_chunks,
        runs=_coalesce(matches),
    )
