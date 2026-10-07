"""Application controllers that bridge use-cases to the main-thread UI."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Optional

from rikai_kotoba.application.disc_workspace import (
    DiscWorkspaceService,
    DiscWorkspaceSnapshot,
)
from rikai_kotoba.application.workers import (
    BackgroundWorkerService,
    WorkerEvent,
    WorkerEventKind,
)


@dataclass(frozen=True)
class DiscControllerEvent:
    kind: str
    snapshot: DiscWorkspaceSnapshot | None = None
    message: str = ""
    job_id: str | None = None


class DiscWorkspaceController:
    """Coordinate disc jobs without importing a presentation toolkit."""

    OPEN_TOPIC = "disc.open"

    def __init__(
        self,
        service: DiscWorkspaceService,
        workers: BackgroundWorkerService,
    ) -> None:
        self.service = service
        self.workers = workers
        self._subscribers: list[Callable[[DiscControllerEvent], object]] = []
        self._active_job_id: Optional[str] = None
        workers.subscribe(self._on_worker_event)

    @property
    def is_busy(self) -> bool:
        return self._active_job_id is not None

    def subscribe(
        self, handler: Callable[[DiscControllerEvent], object]
    ) -> Callable[[DiscControllerEvent], object]:
        if not callable(handler):
            raise TypeError("disc controller subscriber must be callable")
        if handler not in self._subscribers:
            self._subscribers.append(handler)
        return handler

    def _emit(self, event: DiscControllerEvent) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber(event)

    def open_source(self, path: os.PathLike[str] | str) -> str:
        if self.is_busy:
            raise RuntimeError("a disc operation is already running")
        raw_path = os.fspath(path).strip()
        if not raw_path:
            raise ValueError("disc source path must not be empty")
        source_path = os.path.abspath(raw_path)
        job_id = self.workers.submit(
            self.OPEN_TOPIC,
            self.service.open_source,
            source_path,
        )
        self._active_job_id = job_id
        self._emit(
            DiscControllerEvent(
                "opening",
                message=f"Opening {source_path}",
                job_id=job_id,
            )
        )
        return job_id

    def cancel_active(self) -> bool:
        if self._active_job_id is None:
            return False
        return self.workers.cancel(self._active_job_id)

    def close_source(self) -> None:
        if self.is_busy:
            raise RuntimeError("cannot close the disc while an operation is running")
        self.service.close_source()
        self._emit(DiscControllerEvent("closed", message="Disc source closed"))

    def _on_worker_event(self, event: WorkerEvent[object]) -> None:
        if event.topic != self.OPEN_TOPIC:
            return
        if self._active_job_id is not None and event.job_id != self._active_job_id:
            return

        if event.kind is WorkerEventKind.COMPLETED:
            self._active_job_id = None
            snapshot = event.payload
            if not isinstance(snapshot, DiscWorkspaceSnapshot):
                self._emit(
                    DiscControllerEvent(
                        "error",
                        message="Disc worker returned an unexpected result",
                        job_id=event.job_id,
                    )
                )
                return
            self._emit(
                DiscControllerEvent(
                    "opened",
                    snapshot=snapshot,
                    message=(
                        f"Indexed {snapshot.file_count} file(s) and "
                        f"{snapshot.directory_count} directories"
                    ),
                    job_id=event.job_id,
                )
            )
        elif event.kind is WorkerEventKind.FAILED:
            self._active_job_id = None
            label = event.error_type or "Error"
            detail = event.error_message or "Unknown disc-open failure"
            self._emit(
                DiscControllerEvent(
                    "error",
                    message=f"{label}: {detail}",
                    job_id=event.job_id,
                )
            )
        elif event.kind is WorkerEventKind.CANCELLED:
            self._active_job_id = None
            self._emit(
                DiscControllerEvent(
                    "cancelled",
                    message="Disc operation cancelled",
                    job_id=event.job_id,
                )
            )
