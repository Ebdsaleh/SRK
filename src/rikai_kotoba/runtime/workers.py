"""Thread-managed background jobs with main-thread event delivery.

Workers never call Dear PyGui. Results and failures cross the thread boundary as
immutable ``WorkerEvent`` objects. The application runtime calls ``update`` on
its owner thread and subscribers are invoked there.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
import queue
import threading
import traceback
import uuid
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


class WorkerEventKind(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CancellationToken:
    """Cooperative cancellation token for long-running SRK jobs."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise WorkerCancelledError("background job cancelled")


class WorkerCancelledError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerEvent(Generic[T]):
    job_id: str
    topic: str
    kind: WorkerEventKind
    payload: Optional[T] = None
    error_type: str | None = None
    error_message: str | None = None
    traceback_text: str | None = None


@dataclass(frozen=True)
class WorkerSnapshot:
    running: bool
    max_workers: int
    tracked_jobs: int
    queued_events: int


@dataclass
class _JobRecord:
    topic: str
    future: Future[object]
    token: CancellationToken


class BackgroundWorkerService:
    """Lifecycle-managed thread pool whose callbacks are serialized by ``update``."""

    def __init__(self, *, max_workers: int = 2) -> None:
        resolved = int(max_workers)
        if resolved <= 0:
            raise ValueError("max_workers must be positive")
        self.max_workers = resolved
        self._executor: ThreadPoolExecutor | None = None
        self._events: queue.Queue[WorkerEvent[object]] = queue.Queue()
        self._records: dict[str, _JobRecord] = {}
        self._records_lock = threading.Lock()
        self._subscribers: list[Callable[[WorkerEvent[object]], object]] = []
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def subscribe(
        self, handler: Callable[[WorkerEvent[object]], object]
    ) -> Callable[[WorkerEvent[object]], object]:
        if not callable(handler):
            raise TypeError("worker subscriber must be callable")
        if handler not in self._subscribers:
            self._subscribers.append(handler)
        return handler

    def unsubscribe(self, handler: Callable[[WorkerEvent[object]], object]) -> None:
        try:
            self._subscribers.remove(handler)
        except ValueError:
            pass

    def start(self) -> None:
        if self._running:
            return
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="SRKWorker",
        )
        self._running = True

    def submit(
        self,
        topic: str,
        task: Callable[..., T],
        *args: object,
        token: CancellationToken | None = None,
        **kwargs: object,
    ) -> str:
        if not self._running or self._executor is None:
            raise RuntimeError("background worker service is not running")
        name = str(topic or "").strip()
        if not name:
            raise ValueError("worker topic must not be empty")
        if not callable(task):
            raise TypeError("worker task must be callable")

        job_id = uuid.uuid4().hex
        cancel_token = token or CancellationToken()
        self._events.put(WorkerEvent(job_id, name, WorkerEventKind.STARTED))

        def run() -> object:
            if cancel_token.is_cancelled:
                self._events.put(
                    WorkerEvent(job_id, name, WorkerEventKind.CANCELLED)
                )
                return None
            try:
                result = task(*args, **kwargs)
            except WorkerCancelledError:
                self._events.put(
                    WorkerEvent(job_id, name, WorkerEventKind.CANCELLED)
                )
                return None
            except Exception as exc:
                self._events.put(
                    WorkerEvent(
                        job_id,
                        name,
                        WorkerEventKind.FAILED,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        traceback_text="".join(
                            traceback.format_exception(
                                type(exc), exc, exc.__traceback__
                            )
                        ),
                    )
                )
                return None

            if cancel_token.is_cancelled:
                self._events.put(
                    WorkerEvent(job_id, name, WorkerEventKind.CANCELLED)
                )
                return None
            self._events.put(
                WorkerEvent(job_id, name, WorkerEventKind.COMPLETED, payload=result)
            )
            return result

        future = self._executor.submit(run)
        with self._records_lock:
            self._records[job_id] = _JobRecord(name, future, cancel_token)
        return job_id

    def cancel(self, job_id: str) -> bool:
        with self._records_lock:
            record = self._records.get(str(job_id))
        if record is None:
            return False
        record.token.cancel()
        record.future.cancel()
        return True

    def update(self, delta_seconds: float) -> None:
        del delta_seconds
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break

            if event.kind in {
                WorkerEventKind.COMPLETED,
                WorkerEventKind.FAILED,
                WorkerEventKind.CANCELLED,
            }:
                with self._records_lock:
                    self._records.pop(event.job_id, None)

            for subscriber in tuple(self._subscribers):
                subscriber(event)

    def stop(self) -> None:
        if not self._running:
            return
        with self._records_lock:
            records = tuple(self._records.values())
        for record in records:
            record.token.cancel()
            record.future.cancel()

        executor = self._executor
        self._executor = None
        self._running = False
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

        with self._records_lock:
            self._records.clear()
        while True:
            try:
                self._events.get_nowait()
            except queue.Empty:
                break

    def snapshot(self) -> WorkerSnapshot:
        with self._records_lock:
            tracked = len(self._records)
        return WorkerSnapshot(
            running=self._running,
            max_workers=self.max_workers,
            tracked_jobs=tracked,
            queued_events=self._events.qsize(),
        )
