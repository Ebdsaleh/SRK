"""Backend-neutral scene registration and activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SceneHost(Protocol):
    def exists(self, container: object) -> bool:
        ...

    def show(self, container: object) -> None:
        ...

    def hide(self, container: object) -> None:
        ...


@dataclass(frozen=True)
class SceneRecord:
    name: str
    scene: Any
    container: object


class SceneRegistry:
    def __init__(self, host: SceneHost | None = None) -> None:
        self._host = host
        self._records: dict[str, SceneRecord] = {}
        self.current_name: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._records)

    def register(self, name: str, scene: Any, *, container: object) -> Any:
        key = str(name or "").strip()
        if not key:
            raise ValueError("scene name must not be empty")
        if key in self._records:
            raise ValueError(f"scene already registered: {key}")
        if container is None:
            raise ValueError("scene container must not be None")
        self._records[key] = SceneRecord(key, scene, container)
        return scene

    def get(self, name: str) -> Any | None:
        record = self._records.get(str(name))
        return record.scene if record is not None else None

    def active_scene(self) -> Any | None:
        return self.get(self.current_name or "")

    def activate(self, name: str, **kwargs) -> bool:
        record = self._records.get(str(name))
        if record is None:
            return False
        if self._host is None:
            raise RuntimeError("no scene host is installed")

        for other in self._records.values():
            if self._host.exists(other.container):
                self._host.hide(other.container)
        if self._host.exists(record.container):
            self._host.show(record.container)

        self.current_name = record.name
        callback = getattr(record.scene, "on_show", None)
        if callable(callback):
            callback(**kwargs)
        return True
