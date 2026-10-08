"""Application controller for SAROO transport status and memory captures.

The controller owns no GUI objects. Potentially blocking transport and mounted-SD
operations run through SRK's background worker service and immutable events are
delivered back on the application thread during the normal Salix runtime update
cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from rikai_kotoba.application.workers import (
    BackgroundWorkerService,
    WorkerEvent,
    WorkerEventKind,
)
from rikai_kotoba.hardware.saturn.saroo import (
    CaptureArtifact,
    MemoryRange,
    SarooCaptureCoordinator,
    SarooTransportStatus,
)
from rikai_kotoba.hardware.saturn.saroo.capture_ingest import (
    SarooCaptureIngestResult,
    import_saroo_game_work_ram_high_capture,
    import_saroo_work_ram_captures,
)


@dataclass(frozen=True)
class SarooControllerEvent:
    kind: str
    message: str = ""
    job_id: str | None = None
    status: SarooTransportStatus | None = None
    artifact: CaptureArtifact | None = None
    ingest_result: SarooCaptureIngestResult | None = None


class SarooCaptureController:
    STATUS_TOPIC = "saroo.status"
    CAPTURE_TOPIC = "saroo.capture"
    IMPORT_TOPIC = "saroo.import"

    def __init__(
        self,
        coordinator: SarooCaptureCoordinator,
        workers: BackgroundWorkerService,
    ) -> None:
        if not isinstance(coordinator, SarooCaptureCoordinator):
            raise TypeError("SAROO controller requires a SarooCaptureCoordinator")
        if not isinstance(workers, BackgroundWorkerService):
            raise TypeError("SAROO controller requires a BackgroundWorkerService")
        self.coordinator = coordinator
        self.workers = workers
        self._subscribers: list[Callable[[SarooControllerEvent], object]] = []
        self._active_job_id: str | None = None
        self._active_topic: str | None = None
        workers.subscribe(self._on_worker_event)

    @property
    def is_busy(self) -> bool:
        return self._active_job_id is not None

    @property
    def capture_root(self) -> Path:
        return self.coordinator.store.root

    def subscribe(
        self,
        handler: Callable[[SarooControllerEvent], object],
    ) -> Callable[[SarooControllerEvent], object]:
        if not callable(handler):
            raise TypeError("SAROO controller subscriber must be callable")
        if handler not in self._subscribers:
            self._subscribers.append(handler)
        return handler

    def unsubscribe(self, handler: Callable[[SarooControllerEvent], object]) -> None:
        try:
            self._subscribers.remove(handler)
        except ValueError:
            pass

    def _emit(self, event: SarooControllerEvent) -> None:
        for subscriber in tuple(self._subscribers):
            subscriber(event)

    def _start(self, topic: str, task, *args, **kwargs) -> str:
        if self.is_busy:
            raise RuntimeError("a SAROO operation is already running")
        job_id = self.workers.submit(topic, task, *args, **kwargs)
        self._active_job_id = job_id
        self._active_topic = topic
        return job_id

    def refresh_status(self) -> str:
        job_id = self._start(self.STATUS_TOPIC, self.coordinator.status)
        self._emit(
            SarooControllerEvent(
                "checking",
                message="Checking SAROO transport status...",
                job_id=job_id,
            )
        )
        return job_id

    def capture(
        self,
        checkpoint: str,
        ranges: Iterable[MemoryRange],
        *,
        session_label: str = "",
    ) -> str:
        requested = tuple(ranges)
        if not requested:
            raise ValueError("SAROO capture requires at least one memory range")
        job_id = self._start(
            self.CAPTURE_TOPIC,
            self.coordinator.capture,
            checkpoint,
            requested,
            session_label=session_label,
        )
        self._emit(
            SarooControllerEvent(
                "capturing",
                message=f"Capturing {len(requested)} Saturn memory region(s)...",
                job_id=job_id,
            )
        )
        return job_id

    def import_mounted_sd_capture(
        self,
        card_root: str | Path,
        checkpoint: str,
        *,
        session_label: str = "real-hardware",
        game_wramh: bool = True,
    ) -> str:
        """Import verified SAROO capture files from a mounted card, read-only."""

        card_text = str(card_root).strip()
        if not card_text:
            raise ValueError("mounted SAROO card root is required")
        checkpoint_text = str(checkpoint).strip()
        if not checkpoint_text:
            raise ValueError("capture checkpoint label is required")
        session_text = str(session_label).strip()

        importer = (
            import_saroo_game_work_ram_high_capture
            if game_wramh
            else import_saroo_work_ram_captures
        )
        job_id = self._start(
            self.IMPORT_TOPIC,
            importer,
            card_text,
            str(self.capture_root),
            checkpoint=checkpoint_text,
            session_label=session_text,
        )
        mode = "in-game WRAM-H" if game_wramh else "menu WRAM-L + WRAM-H"
        self._emit(
            SarooControllerEvent(
                "importing",
                message=f"Importing mounted-card {mode} capture...",
                job_id=job_id,
            )
        )
        return job_id

    def cancel_active(self) -> bool:
        if self._active_job_id is None:
            return False
        return self.workers.cancel(self._active_job_id)

    def _finish(self) -> tuple[str | None, str | None]:
        job_id = self._active_job_id
        topic = self._active_topic
        self._active_job_id = None
        self._active_topic = None
        return job_id, topic

    def _on_worker_event(self, event: WorkerEvent[object]) -> None:
        if event.topic not in {self.STATUS_TOPIC, self.CAPTURE_TOPIC, self.IMPORT_TOPIC}:
            return
        if self._active_job_id is None or event.job_id != self._active_job_id:
            return
        if event.kind is WorkerEventKind.STARTED:
            return

        job_id, topic = self._finish()
        if event.kind is WorkerEventKind.COMPLETED:
            if topic == self.STATUS_TOPIC:
                status = event.payload
                if not isinstance(status, SarooTransportStatus):
                    self._emit(
                        SarooControllerEvent(
                            "error",
                            message="SAROO status worker returned an unexpected result",
                            job_id=job_id,
                        )
                    )
                    return
                self._emit(
                    SarooControllerEvent(
                        "status",
                        message=status.detail,
                        job_id=job_id,
                        status=status,
                    )
                )
                return

            if topic == self.IMPORT_TOPIC:
                ingest_result = event.payload
                if not isinstance(ingest_result, SarooCaptureIngestResult):
                    self._emit(
                        SarooControllerEvent(
                            "error",
                            message="SAROO import worker returned an unexpected result",
                            job_id=job_id,
                        )
                    )
                    return
                self._emit(
                    SarooControllerEvent(
                        "imported",
                        message=(
                            "Mounted-card capture imported and verified at "
                            f"{ingest_result.artifact.directory}"
                        ),
                        job_id=job_id,
                        artifact=ingest_result.artifact,
                        ingest_result=ingest_result,
                    )
                )
                return

            artifact = event.payload
            if not isinstance(artifact, CaptureArtifact):
                self._emit(
                    SarooControllerEvent(
                        "error",
                        message="SAROO capture worker returned an unexpected result",
                        job_id=job_id,
                    )
                )
                return
            self._emit(
                SarooControllerEvent(
                    "captured",
                    message=f"Capture saved to {artifact.directory}",
                    job_id=job_id,
                    artifact=artifact,
                )
            )
            return

        if event.kind is WorkerEventKind.CANCELLED:
            self._emit(
                SarooControllerEvent(
                    "cancelled",
                    message="SAROO operation cancelled",
                    job_id=job_id,
                )
            )
            return

        if event.kind is WorkerEventKind.FAILED:
            label = event.error_type or "Error"
            detail = event.error_message or "Unknown SAROO operation failure"
            self._emit(
                SarooControllerEvent(
                    "error",
                    message=f"{label}: {detail}",
                    job_id=job_id,
                )
            )

    def close(self) -> None:
        self.coordinator.close()
