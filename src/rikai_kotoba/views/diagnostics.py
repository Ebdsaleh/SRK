"""Runtime diagnostics scene for the SRK desktop application."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from rikai_kotoba.application.workers import BackgroundWorkerService
from salix.runtime.diagnostics import ExceptionReporter
from salix.runtime.lifecycle import ApplicationRuntime


class DiagnosticsView:
    def __init__(
        self,
        runtime: ApplicationRuntime,
        workers: BackgroundWorkerService,
        reporter: ExceptionReporter,
    ) -> None:
        self.runtime = runtime
        self.workers = workers
        self.reporter = reporter
        self._elapsed = 0.0
        self._built = False

    def build(self, parent: str | int) -> None:
        self._built = True
        dpg.add_text("DIAGNOSTICS", parent=parent, color=(180, 160, 255))
        dpg.add_text(
            "Application services are supervised by the backend-neutral Salix runtime; Dear PyGui owns presentation only.",
            parent=parent,
            color=(180, 180, 180),
            wrap=1050,
        )
        dpg.add_separator(parent=parent)
        self.runtime_text = dpg.add_text(parent=parent)
        self.worker_text = dpg.add_text(parent=parent)
        self.queue_text = dpg.add_text(parent=parent)
        log_path = str(self.reporter.log_path) if self.reporter.log_path else "Disabled"
        dpg.add_text(f"UI error log: {log_path}", parent=parent, wrap=1050)
        dpg.add_spacer(height=8, parent=parent)
        dpg.add_text(
            "Thread rule: only the Dear PyGui owner thread may touch widgets. Background workers return immutable events and Salix dispatches service updates on the application thread.",
            parent=parent,
            wrap=1050,
            color=(150, 190, 255),
        )
        self._refresh()

    def _refresh(self) -> None:
        if not self._built:
            return
        snapshot = self.workers.snapshot()
        dpg.set_value(
            self.runtime_text,
            f"Salix application runtime: {self.runtime.state.value}",
        )
        dpg.set_value(
            self.worker_text,
            f"Background workers: {'running' if snapshot.running else 'stopped'} | pool={snapshot.max_workers} | tracked jobs={snapshot.tracked_jobs}",
        )
        dpg.set_value(
            self.queue_text,
            f"Pending worker events: {snapshot.queued_events}",
        )

    def update(self, delta_seconds: float) -> None:
        self._elapsed += max(0.0, float(delta_seconds))
        if self._elapsed >= 0.25:
            self._elapsed = 0.0
            self._refresh()
