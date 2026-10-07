"""Transport-neutral SAROO capture contracts.

SRK does not guess how a particular SAROO firmware exposes Saturn memory. The
application asks this protocol for address ranges; a concrete transport adapter
may later use SD-card exchange, serial/USB, shared files, or another verified
mechanism without changing capture persistence or provenance analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol, runtime_checkable

from .capture import CaptureArtifact, CaptureStore, CapturedRegion, MemoryRange


class SarooTransportError(RuntimeError):
    """Base error for SAROO transport operations."""


class SarooTransportUnavailableError(SarooTransportError):
    """Raised when capture is requested without an available transport."""


@dataclass(frozen=True)
class SarooTransportStatus:
    """Presentation-neutral transport availability snapshot."""

    name: str
    available: bool
    detail: str = ""

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise ValueError("transport status name must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "available", bool(self.available))
        object.__setattr__(self, "detail", str(self.detail or "").strip())


@runtime_checkable
class SarooTransport(Protocol):
    """Minimal address-range transport consumed by the capture coordinator."""

    def status(self) -> SarooTransportStatus:
        ...

    def read_memory(self, memory_range: MemoryRange) -> bytes:
        ...

    def close(self) -> None:
        ...


def _transport_contract_errors(transport: object) -> tuple[str, ...]:
    required = ("status", "read_memory", "close")
    return tuple(name for name in required if not callable(getattr(transport, name, None)))


class UnconfiguredSarooTransport:
    """Explicit placeholder used until a verified hardware adapter is installed."""

    def status(self) -> SarooTransportStatus:
        return SarooTransportStatus(
            name="unconfigured",
            available=False,
            detail="No verified SAROO transport adapter is configured.",
        )

    def read_memory(self, memory_range: MemoryRange) -> bytes:
        del memory_range
        raise SarooTransportUnavailableError(
            "no verified SAROO transport adapter is configured"
        )

    def close(self) -> None:
        return None


class SarooCaptureCoordinator:
    """Read caller-supplied Saturn ranges and publish one capture artifact.

    This object is synchronous by design. GUI applications should call
    :meth:`capture` through their normal background-worker boundary; the
    coordinator itself never imports or calls a presentation toolkit.
    """

    def __init__(self, transport: SarooTransport, store: CaptureStore):
        missing = _transport_contract_errors(transport)
        if missing:
            raise TypeError(
                "SAROO transport does not satisfy the capture contract; missing: "
                + ", ".join(missing)
            )
        if not isinstance(store, CaptureStore):
            raise TypeError("SAROO capture coordinator requires a CaptureStore")
        self.transport = transport
        self.store = store

    def status(self) -> SarooTransportStatus:
        status = self.transport.status()
        if not isinstance(status, SarooTransportStatus):
            raise SarooTransportError("SAROO transport returned an invalid status object")
        return status

    def capture(
        self,
        checkpoint: str,
        ranges: Iterable[MemoryRange],
        *,
        captured_at: datetime | None = None,
        session_label: str = "",
    ) -> CaptureArtifact:
        requested = tuple(ranges)
        if not requested:
            raise ValueError("SAROO capture requires at least one memory range")
        if any(not isinstance(memory_range, MemoryRange) for memory_range in requested):
            raise TypeError("SAROO capture ranges must be MemoryRange instances")

        status = self.status()
        if not status.available:
            detail = f": {status.detail}" if status.detail else ""
            raise SarooTransportUnavailableError(
                f"SAROO transport {status.name!r} is unavailable{detail}"
            )

        captured: list[CapturedRegion] = []
        for memory_range in requested:
            try:
                payload = self.transport.read_memory(memory_range)
                captured.append(CapturedRegion(memory_range, payload))
            except SarooTransportError:
                raise
            except Exception as exc:
                label = memory_range.label or f"0x{memory_range.start_address:08X}"
                raise SarooTransportError(
                    f"failed to capture {label}: {type(exc).__name__}: {exc}"
                ) from exc

        return self.store.save(
            checkpoint,
            captured,
            captured_at=captured_at,
            session_label=session_label,
        )

    def close(self) -> None:
        self.transport.close()
