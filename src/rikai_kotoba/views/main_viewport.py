"""SRK desktop composition root for Dear PyGui views."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from rikai_kotoba.application.controller import DiscWorkspaceController
from rikai_kotoba.engine.gui_engine import GuiEngine
from rikai_kotoba.runtime.diagnostics import ExceptionReporter
from rikai_kotoba.runtime.workers import BackgroundWorkerService
from rikai_kotoba.views.diagnostics import DiagnosticsView
from rikai_kotoba.views.disc_workspace import DiscWorkspaceView
from rikai_kotoba.views.saroo import SarooView


class MainViewport:
    def __init__(
        self,
        engine: GuiEngine,
        disc_controller: DiscWorkspaceController,
        workers: BackgroundWorkerService,
        reporter: ExceptionReporter,
        *,
        initial_source: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.engine = engine
        self.disc_view = DiscWorkspaceView(
            disc_controller,
            initial_source=initial_source,
            output_dir=output_dir,
        )
        self.saroo_view = SarooView()
        self.diagnostics_view = DiagnosticsView(engine.runtime, workers, reporter)
        self._build()

    def _show_about(self) -> None:
        dpg.configure_item("srk_about_window", show=True)

    def _build_menu(self, parent: str | int) -> None:
        with dpg.menu_bar(parent=parent):
            with dpg.menu(label="File"):
                dpg.add_menu_item(
                    label="Open Disc Image...",
                    callback=lambda: self.disc_view.show_source_dialog(),
                )
                dpg.add_separator()
                dpg.add_menu_item(label="Exit", callback=lambda: self.engine.request_stop())
            with dpg.menu(label="View"):
                dpg.add_menu_item(
                    label="Disc Workspace",
                    callback=lambda: self.engine.switch_scene("disc"),
                )
                dpg.add_menu_item(
                    label="Saturn / SAROO",
                    callback=lambda: self.engine.switch_scene("saroo"),
                )
                dpg.add_menu_item(
                    label="Diagnostics",
                    callback=lambda: self.engine.switch_scene("diagnostics"),
                )
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About SRK", callback=lambda: self._show_about())

    def _build(self) -> None:
        with dpg.window(
            tag="srk_primary_window",
            no_title_bar=True,
            no_resize=True,
            no_move=True,
        ):
            self._build_menu("srk_primary_window")
            with dpg.group(horizontal=True):
                dpg.add_text("SRK // SALIX RIKAI KOTOBA", color=(80, 220, 160))
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Disc Workspace",
                    callback=lambda: self.engine.switch_scene("disc"),
                )
                dpg.add_button(
                    label="Saturn / SAROO",
                    callback=lambda: self.engine.switch_scene("saroo"),
                )
                dpg.add_button(
                    label="Diagnostics",
                    callback=lambda: self.engine.switch_scene("diagnostics"),
                )
            dpg.add_separator()

            with dpg.child_window(
                tag="srk_scene_disc",
                width=-1,
                height=-1,
                border=False,
            ):
                self.disc_view.build("srk_scene_disc")
            self.engine.register_scene("disc", self.disc_view, container="srk_scene_disc")

            with dpg.child_window(
                tag="srk_scene_saroo",
                width=-1,
                height=-1,
                border=False,
                show=False,
            ):
                self.saroo_view.build("srk_scene_saroo")
            self.engine.register_scene("saroo", self.saroo_view, container="srk_scene_saroo")

            with dpg.child_window(
                tag="srk_scene_diagnostics",
                width=-1,
                height=-1,
                border=False,
                show=False,
            ):
                self.diagnostics_view.build("srk_scene_diagnostics")
            self.engine.register_scene(
                "diagnostics",
                self.diagnostics_view,
                container="srk_scene_diagnostics",
            )

        with dpg.window(
            tag="srk_about_window",
            label="About SRK",
            modal=True,
            show=False,
            no_resize=True,
            width=520,
            height=220,
        ):
            dpg.add_text("SRK — Salix Rikai Kotoba", color=(80, 220, 160))
            dpg.add_text(
                "Retro-disc localization, reverse-engineering, and original-hardware research framework.",
                wrap=470,
            )
            dpg.add_spacer(height=8)
            dpg.add_text(
                "Original source media is read-only by policy. Title-specific research stays outside the reusable public core.",
                wrap=470,
            )
            dpg.add_spacer(height=8)
            dpg.add_button(
                label="Close",
                callback=lambda: dpg.configure_item("srk_about_window", show=False),
            )

        dpg.set_primary_window("srk_primary_window", True)
        self.engine.switch_scene("disc")
