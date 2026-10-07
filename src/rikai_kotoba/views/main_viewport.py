"""SRK desktop composition root built on the Salix Dear PyGui application host."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from rikai_kotoba.application.controller import DiscWorkspaceController
from rikai_kotoba.application.workers import BackgroundWorkerService
from rikai_kotoba.views.diagnostics import DiagnosticsView
from rikai_kotoba.views.disc_workspace import DiscWorkspaceView
from rikai_kotoba.views.help import HelpView
from rikai_kotoba.views.saroo import SarooView
from salix.engine.application_hosts import DearPyGuiApplicationHost
from salix.framework.components import Button, ComponentEvent, Label
from salix.runtime.diagnostics import ExceptionReporter


class MainViewport:
    """Compose SRK product views around the reusable Salix desktop host."""

    def __init__(
        self,
        host: DearPyGuiApplicationHost,
        disc_controller: DiscWorkspaceController,
        workers: BackgroundWorkerService,
        reporter: ExceptionReporter,
        *,
        initial_source: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.host = host
        self.disc_view = DiscWorkspaceView(
            disc_controller,
            initial_source=initial_source,
            output_dir=output_dir,
        )
        self.saroo_view = SarooView()
        self.diagnostics_view = DiagnosticsView(host.runtime, workers, reporter)
        self.help_view = HelpView(host.layout)
        self._build()

    def _show_about(self) -> None:
        dpg.configure_item("srk_about_window", show=True)

    def _switch_scene(self, name: str) -> bool:
        changed = self.host.scenes.activate(name)
        if changed:
            self.host.layout.refresh_all()
        return changed

    def _build_menu(self, parent: str | int) -> None:
        """Build application chrome; actions delegate into Salix-owned host state."""

        with dpg.menu_bar(parent=parent):
            with dpg.menu(label="File"):
                dpg.add_menu_item(
                    label="Open Disc Image...",
                    callback=lambda *_args: self.disc_view.show_source_dialog(),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="Exit",
                    callback=lambda *_args: self.host.request_stop(),
                )
            with dpg.menu(label="View"):
                dpg.add_menu_item(
                    label="Disc Workspace",
                    callback=lambda *_args: self._switch_scene("disc"),
                )
                dpg.add_menu_item(
                    label="Saturn / SAROO",
                    callback=lambda *_args: self._switch_scene("saroo"),
                )
                dpg.add_menu_item(
                    label="Diagnostics",
                    callback=lambda *_args: self._switch_scene("diagnostics"),
                )
            with dpg.menu(label="Help"):
                dpg.add_menu_item(
                    label="Offline Manual & Glossary",
                    callback=lambda *_args: self._switch_scene("help"),
                )
                dpg.add_separator()
                dpg.add_menu_item(
                    label="About SRK",
                    callback=lambda *_args: self._show_about(),
                )

    def _button(self, label: str, scene: str) -> Button:
        return Button(
            label,
            callback=lambda _event, target=scene: self._switch_scene(target),
        )

    def _build_header(self, parent: str | int) -> None:
        renderer = self.host.component_renderer
        with renderer.container("row", parent=parent) as row:
            Label("SRK // SALIX RIKAI KOTOBA", color=(80, 220, 160)).build(
                renderer=renderer,
                parent=row,
            )
            self._button("Disc Workspace", "disc").build(renderer=renderer, parent=row)
            self._button("Saturn / SAROO", "saroo").build(renderer=renderer, parent=row)
            self._button("Diagnostics", "diagnostics").build(renderer=renderer, parent=row)
            self._button("Help", "help").build(renderer=renderer, parent=row)
        dpg.add_separator(parent=parent)

    def _build_scene(self, tag: str, view: object, *, show: bool) -> None:
        with dpg.child_window(
            tag=tag,
            parent=self.host.root,
            width=-1,
            height=-1,
            border=False,
            show=show,
        ):
            build = getattr(view, "build", None)
            if callable(build):
                build(tag)
        self.host.scenes.register(tag.removeprefix("srk_scene_"), view, container=tag)

    def _build(self) -> None:
        self._build_menu(self.host.root)
        self._build_header(self.host.root)

        self._build_scene("srk_scene_disc", self.disc_view, show=True)
        self._build_scene("srk_scene_saroo", self.saroo_view, show=False)
        self._build_scene("srk_scene_diagnostics", self.diagnostics_view, show=False)
        self._build_scene("srk_scene_help", self.help_view, show=False)

        with dpg.window(
            tag="srk_about_window",
            label="About SRK",
            modal=True,
            show=False,
            no_resize=True,
            width=560,
            height=250,
        ):
            dpg.add_text("SRK — Salix Rikai Kotoba", color=(80, 220, 160))
            dpg.add_text(
                "Retro-disc localization, reverse-engineering, and original-hardware research framework built on the Salix RAD architecture.",
                wrap=510,
            )
            dpg.add_spacer(height=8)
            dpg.add_text(
                "Original source media is read-only by policy. Title-specific research stays outside the reusable public core.",
                wrap=510,
            )
            dpg.add_spacer(height=8)
            dpg.add_button(
                label="Close",
                callback=lambda *_args: dpg.configure_item(
                    "srk_about_window",
                    show=False,
                ),
            )

        self._switch_scene("disc")

    def update(self, delta_seconds: float) -> None:
        active = self.host.scenes.active_scene()
        update = getattr(active, "update", None)
        if callable(update):
            update(delta_seconds)

    def dispose(self) -> None:
        self.help_view.dispose()
