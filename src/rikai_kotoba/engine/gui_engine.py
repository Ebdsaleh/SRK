"""Dear PyGui host and main-thread runtime loop for SRK."""

from __future__ import annotations

import time

import dearpygui.dearpygui as dpg

from rikai_kotoba.runtime.application import ApplicationSpec
from rikai_kotoba.runtime.diagnostics import ExceptionReporter
from rikai_kotoba.runtime.lifecycle import ApplicationRuntime, CallbackService
from rikai_kotoba.runtime.scenes import SceneRegistry
from rikai_kotoba.engine.scene_host import DearPyGuiSceneHost


def _dpg_version_tuple() -> tuple[int, int, int]:
    try:
        raw = str(dpg.get_dearpygui_version() or "0")
    except Exception:
        return (0, 0, 0)
    values: list[int] = []
    for part in raw.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        values.append(int(digits or 0))
        if len(values) == 3:
            break
    while len(values) < 3:
        values.append(0)
    return tuple(values[:3])  # type: ignore[return-value]


class GuiEngine:
    """Own Dear PyGui while the application runtime remains toolkit-neutral.

    Dear PyGui callback jobs are drained explicitly on the same thread that
    performs runtime updates and rendering. Background services communicate by
    queues and must never manipulate Dear PyGui state directly.
    """

    def __init__(
        self,
        spec: ApplicationSpec,
        *,
        runtime: ApplicationRuntime,
        error_reporter: ExceptionReporter,
    ) -> None:
        self.spec = spec
        self.runtime = runtime
        self.error_reporter = error_reporter
        self.scenes = SceneRegistry(DearPyGuiSceneHost())
        self._closed = False
        self._manual_callbacks = False

        dpg.create_context()
        if _dpg_version_tuple() >= (2, 2, 0):
            dpg.configure_app(manual_callback_management=True)
            self._manual_callbacks = True

        dpg.create_viewport(
            title=self.spec.title,
            width=self.spec.width,
            height=self.spec.height,
        )
        try:
            dpg.set_viewport_min_width(self.spec.minimum_width)
            dpg.set_viewport_min_height(self.spec.minimum_height)
        except Exception:
            pass
        dpg.setup_dearpygui()

        self.runtime.services.register(
            "active scene update",
            CallbackService(on_update=self._update_active_scene),
        )

    def _report(self, context: str, exc: BaseException) -> None:
        self.error_reporter.report(context, exc)

    def _update_active_scene(self, delta_seconds: float) -> None:
        active = self.scenes.active_scene()
        update = getattr(active, "update", None)
        if callable(update):
            update(delta_seconds)

    def register_scene(self, name: str, scene: object, *, container: object) -> None:
        self.scenes.register(name, scene, container=container)

    def switch_scene(self, name: str, **kwargs: object) -> bool:
        return self.scenes.activate(name, **kwargs)

    def request_stop(self) -> None:
        try:
            dpg.stop_dearpygui()
        except Exception:
            pass

    def _run_dpg_callbacks(self) -> None:
        if not self._manual_callbacks:
            return
        try:
            jobs = dpg.get_callback_queue()
        except Exception as exc:
            self._report("DearPyGui callback queue", exc)
            return
        if not jobs:
            return
        for job in jobs:
            try:
                dpg.run_callbacks([job])
            except Exception as exc:
                callback_name = (
                    getattr(job[0], "__name__", repr(job[0])) if job else "unknown"
                )
                self._report(f"DearPyGui callback {callback_name}", exc)

    def run(self) -> int:
        dpg.show_viewport()
        last_frame_at = time.monotonic()
        try:
            self.runtime.start()
            while dpg.is_dearpygui_running():
                self._run_dpg_callbacks()
                now = time.monotonic()
                delta_seconds = max(0.0, min(1.0, now - last_frame_at))
                last_frame_at = now
                self.runtime.update(delta_seconds)
                try:
                    dpg.render_dearpygui_frame()
                except Exception as exc:
                    self._report("DearPyGui render", exc)
            return 0
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.runtime.stop()
        finally:
            try:
                dpg.destroy_context()
            except Exception:
                pass
