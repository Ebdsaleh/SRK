"""Verified SAROO SD-file capture exchange primitives.

This module models the file-writing behavior used by the Saturn-side helper
without depending on a concrete firmware trigger.  Upstream SAROO exposes a
Saturn-side ``write_file(name, offset, size, buf)`` primitive.  SRK deliberately
keeps trigger mechanics (shell command, breakpoint hook, hotkey, etc.) separate
from the capture-file format and import path.

The default transfer chunk is 64 KiB.  That size is grounded in upstream SAROO's
own Saturn-side ``fwt`` diagnostic, which calls ``write_file`` with ``0x10000``
bytes from Saturn memory.  Larger unverified staging writes are not assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .capture import CaptureArtifact, CaptureStore, CapturedRegion, MemoryRange


SAROO_SD_WRITE_CHUNK_SIZE = 0x10000


@dataclass(frozen=True)
class SarooSdWriteChunk:
    """One verified-size Saturn-memory to SD-file write operation."""

    source_address: int
    file_offset: int
    size: int
    truncate: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.source_address, bool) or not isinstance(self.source_address, int):
            raise TypeError("source_address must be an integer")
        if isinstance(self.file_offset, bool) or not isinstance(self.file_offset, int):
            raise TypeError("file_offset must be an integer")
        if isinstance(self.size, bool) or not isinstance(self.size, int):
            raise TypeError("size must be an integer")
        if self.source_address < 0 or self.source_address >= (1 << 32):
            raise ValueError("source_address must fit in 32 bits")
        if self.file_offset < 0:
            raise ValueError("file_offset must be non-negative")
        if self.size <= 0:
            raise ValueError("chunk size must be positive")
        if self.source_address + self.size > (1 << 32):
            raise ValueError("chunk extends past 32-bit address space")
        object.__setattr__(self, "truncate", bool(self.truncate))

    @property
    def upstream_write_offset(self) -> int:
        """Offset passed to upstream ``write_file``.

        SAROO's MCU handler interprets ``-1`` as create/truncate and then seeks
        to offset zero.  Subsequent chunks use their explicit non-negative file
        offsets.
        """

        return -1 if self.truncate else self.file_offset


def plan_sd_write_chunks(
    memory_range: MemoryRange,
    *,
    chunk_size: int = SAROO_SD_WRITE_CHUNK_SIZE,
) -> tuple[SarooSdWriteChunk, ...]:
    """Plan a range as deterministic create-then-offset chunked SD writes."""

    if not isinstance(memory_range, MemoryRange):
        raise TypeError("memory_range must be a MemoryRange")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an integer")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_size > SAROO_SD_WRITE_CHUNK_SIZE:
        raise ValueError(
            "chunk_size exceeds SRK's currently verified SAROO staging size "
            f"(0x{SAROO_SD_WRITE_CHUNK_SIZE:X})"
        )

    chunks: list[SarooSdWriteChunk] = []
    remaining = memory_range.size
    offset = 0
    while remaining:
        size = min(chunk_size, remaining)
        chunks.append(
            SarooSdWriteChunk(
                source_address=memory_range.start_address + offset,
                file_offset=offset,
                size=size,
                truncate=(offset == 0),
            )
        )
        offset += size
        remaining -= size
    return tuple(chunks)


def import_raw_sd_dump(
    path: str | Path,
    *,
    base_address: int,
    checkpoint: str,
    store: CaptureStore,
    label: str = "",
    session_label: str = "",
    expected_size: int | None = None,
) -> CaptureArtifact:
    """Import one raw SAROO-produced SD file into SRK's capture store.

    The raw source file is read-only.  A new immutable SRK capture artifact is
    created beneath ``store`` with SHA-256 metadata and the supplied Saturn base
    address.
    """

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SAROO raw dump does not exist: {source}")
    payload = source.read_bytes()
    if not payload:
        raise ValueError("SAROO raw dump is empty")
    if expected_size is not None:
        if isinstance(expected_size, bool) or not isinstance(expected_size, int):
            raise TypeError("expected_size must be an integer or None")
        if expected_size <= 0:
            raise ValueError("expected_size must be positive")
        if len(payload) != expected_size:
            raise ValueError(
                "SAROO raw dump size does not match expected size "
                f"({len(payload)} != {expected_size})"
            )

    memory_range = MemoryRange(
        start_address=int(base_address),
        size=len(payload),
        label=label,
    )
    return store.save(
        checkpoint,
        (CapturedRegion(memory_range, payload),),
        session_label=session_label,
    )


def total_planned_bytes(chunks: Iterable[SarooSdWriteChunk]) -> int:
    """Return the total payload represented by a write plan."""

    total = 0
    for chunk in chunks:
        if not isinstance(chunk, SarooSdWriteChunk):
            raise TypeError("chunks must contain SarooSdWriteChunk values")
        total += chunk.size
    return total
