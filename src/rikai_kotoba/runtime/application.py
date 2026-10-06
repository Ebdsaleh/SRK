"""Backend-neutral application metadata for SRK desktop hosts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field} must be an integer") from exc
    if resolved <= 0:
        raise ValueError(f"{field} must be positive")
    return resolved


@dataclass(frozen=True)
class ApplicationSpec:
    """Toolkit-neutral description of SRK's root application window."""

    name: str
    title: str | None = None
    width: int = 1180
    height: int = 760
    minimum_width: int = 1000
    minimum_height: int = 640
    target_fps: int = 60

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise ValueError("application name must not be empty")
        title = name if self.title is None else str(self.title).strip()
        if not title:
            title = name

        width = _positive_int(self.width, field="application width")
        height = _positive_int(self.height, field="application height")
        minimum_width = _positive_int(
            self.minimum_width, field="application minimum width"
        )
        minimum_height = _positive_int(
            self.minimum_height, field="application minimum height"
        )
        target_fps = _positive_int(self.target_fps, field="application target_fps")

        if minimum_width > width:
            raise ValueError("application minimum width must not exceed width")
        if minimum_height > height:
            raise ValueError("application minimum height must not exceed height")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "minimum_width", minimum_width)
        object.__setattr__(self, "minimum_height", minimum_height)
        object.__setattr__(self, "target_fps", target_fps)

    @property
    def frame_interval_seconds(self) -> float:
        return 1.0 / float(self.target_fps)


@runtime_checkable
class ApplicationHost(Protocol):
    """Minimal lifecycle surface implemented by concrete presentation hosts."""

    spec: ApplicationSpec
    runtime: object

    def run(self) -> int:
        ...

    def request_stop(self) -> None:
        ...
