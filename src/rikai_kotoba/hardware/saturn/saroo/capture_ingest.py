"""Import controller-generated SAROO Work RAM captures into SRK evidence storage.

The mounted SD card is treated as read-only input. Known SRK capture files are
validated against their canonical Saturn ranges, summarized, copied into one
immutable CaptureStore artifact, and then verified from the off-card copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os

from .capture import CaptureArtifact, CaptureStore, CapturedRegion, MemoryRange, verify_capture


SAROO_WRAML_RELATIVE_PATH = "SAROO/SRK_WRAML.BIN"
SAROO_WRAMH_RELATIVE_PATH = "SAROO/SRK_WRAMH.BIN"
SAROO_WORK_RAM_SIZE = 0x00100000
SAROO_WRAML_RANGE = MemoryRange(0x00200000, SAROO_WORK_RAM_SIZE, "work-ram-low")
SAROO_WRAMH_RANGE = MemoryRange(0x06000000, SAROO_WORK_RAM_SIZE, "work-ram-high")


class SarooCaptureIngestError(RuntimeError):
    """Raised when a hardware-produced capture cannot be safely imported."""


@dataclass(frozen=True)
class SarooRawCaptureSummary:
    relative_path: str
    source_path: Path
    memory_range: MemoryRange
    size: int
    sha256: str
    zero_bytes: int
    nonzero_bytes: int
    first_nonzero_offset: int | None
    last_nonzero_offset: int | None

    @property
    def first_nonzero_address(self) -> int | None:
        if self.first_nonzero_offset is None:
            return None
        return self.memory_range.start_address + self.first_nonzero_offset

    @property
    def last_nonzero_address(self) -> int | None:
        if self.last_nonzero_offset is None:
            return None
        return self.memory_range.start_address + self.last_nonzero_offset


@dataclass(frozen=True)
class SarooCaptureIngestResult:
    card_root: Path
    artifact: CaptureArtifact
    summaries: tuple[SarooRawCaptureSummary, ...]


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _payload_nonzero_summary(payload: bytes) -> tuple[int, int | None, int | None]:
    count = 0
    first: int | None = None
    last: int | None = None
    for index, value in enumerate(payload):
        if value == 0:
            continue
        count += 1
        if first is None:
            first = index
        last = index
    return count, first, last


def _read_capture(
    card_root: Path,
    relative_path: str,
    memory_range: MemoryRange,
) -> tuple[SarooRawCaptureSummary, CapturedRegion]:
    source = card_root / Path(relative_path)
    if not source.is_file():
        raise SarooCaptureIngestError(f"expected SAROO capture is missing: {source}")
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise SarooCaptureIngestError(f"cannot read SAROO capture {source}: {exc}") from exc
    if len(payload) != memory_range.size:
        raise SarooCaptureIngestError(
            f"SAROO capture has unexpected size: {relative_path} "
            f"({len(payload)} != {memory_range.size})"
        )

    nonzero_count, first_nonzero, last_nonzero = _payload_nonzero_summary(payload)
    summary = SarooRawCaptureSummary(
        relative_path=relative_path,
        source_path=source,
        memory_range=memory_range,
        size=len(payload),
        sha256=sha256(payload).hexdigest(),
        zero_bytes=len(payload) - nonzero_count,
        nonzero_bytes=nonzero_count,
        first_nonzero_offset=first_nonzero,
        last_nonzero_offset=last_nonzero,
    )
    return summary, CapturedRegion(memory_range, payload)


def import_saroo_work_ram_captures(
    card_root: os.PathLike[str] | str,
    store_root: os.PathLike[str] | str,
    *,
    checkpoint: str = "saroo-menu",
    session_label: str = "real-hardware",
) -> SarooCaptureIngestResult:
    """Import both SRK Work RAM files without modifying the mounted card."""

    card = _canonical(card_root)
    store_path = _canonical(store_root)
    if not card.is_dir():
        raise SarooCaptureIngestError(f"SAROO card root is not a directory: {card}")
    if _inside(store_path, card):
        raise SarooCaptureIngestError("capture store must be outside the mounted SAROO card")

    summaries: list[SarooRawCaptureSummary] = []
    regions: list[CapturedRegion] = []
    for relative_path, memory_range in (
        (SAROO_WRAML_RELATIVE_PATH, SAROO_WRAML_RANGE),
        (SAROO_WRAMH_RELATIVE_PATH, SAROO_WRAMH_RANGE),
    ):
        summary, region = _read_capture(card, relative_path, memory_range)
        summaries.append(summary)
        regions.append(region)

    store = CaptureStore(store_path)
    artifact = store.save(
        checkpoint,
        regions,
        session_label=session_label,
    )
    verification = verify_capture(artifact.directory)
    if not verification.valid:
        raise SarooCaptureIngestError(
            "off-card capture artifact failed verification: " + "; ".join(verification.errors)
        )

    return SarooCaptureIngestResult(
        card_root=card,
        artifact=artifact,
        summaries=tuple(summaries),
    )
