"""Dear PyGui presentation for SRK's read-only disc workspace."""

from __future__ import annotations

import os
from typing import Any

import dearpygui.dearpygui as dpg

from rikai_kotoba.application.controller import (
    DiscControllerEvent,
    DiscWorkspaceController,
)
from rikai_kotoba.application.disc_workspace import (
    DiscEntrySnapshot,
    DiscWorkspaceSnapshot,
)


class DiscWorkspaceView:
    def __init__(
        self,
        controller: DiscWorkspaceController,
        *,
        initial_source: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.controller = controller
        self.initial_source = os.path.abspath(initial_source) if initial_source else ""
        self.output_dir = os.path.abspath(output_dir or os.getcwd())
        self._pending_initial_source = self.initial_source or None
        self._table_rows: list[str] = []
        self._snapshot: DiscWorkspaceSnapshot | None = None
        self._selected_entry: DiscEntrySnapshot | None = None
        self._built = False
        controller.subscribe(self._on_controller_event)

    @staticmethod
    def _dialog_selection(app_data: Any) -> str:
        if not isinstance(app_data, dict):
            return ""
        direct = app_data.get("file_path_name")
        if direct:
            return os.path.abspath(str(direct))
        selections = app_data.get("selections")
        if isinstance(selections, dict) and selections:
            return os.path.abspath(str(next(iter(selections.values()))))
        current = app_data.get("current_path")
        if current:
            return os.path.abspath(str(current))
        return ""

    def build(self, parent: str | int) -> None:
        self._built = True
        dpg.add_text("DISC WORKSPACE", parent=parent, color=(80, 220, 160))
        dpg.add_text(
            "Read-only disc inspection. Opening and ISO-9660 indexing run on SRK background workers; Dear PyGui remains on the main thread.",
            parent=parent,
            wrap=1050,
            color=(180, 180, 180),
        )
        dpg.add_spacer(height=8, parent=parent)

        with dpg.group(parent=parent):
            dpg.add_text("Disc image / CUE")
            with dpg.group(horizontal=True):
                self.source_input = dpg.add_input_text(
                    default_value=self.initial_source,
                    width=-285,
                    hint="Choose a .cue, .iso, .bin, .img, or .raw image",
                )
                dpg.add_button(
                    label="Browse Image...",
                    width=130,
                    callback=lambda: dpg.show_item(self.source_dialog),
                )
                self.open_button = dpg.add_button(
                    label="Open / Scan",
                    width=120,
                    callback=self._open_source,
                )

            dpg.add_text("Output workspace")
            with dpg.group(horizontal=True):
                self.output_input = dpg.add_input_text(
                    default_value=self.output_dir,
                    width=-155,
                    hint="Generated artifacts will be rooted here",
                )
                dpg.add_button(
                    label="Browse Folder...",
                    width=130,
                    callback=lambda: dpg.show_item(self.output_dialog),
                )

        dpg.add_separator(parent=parent)
        self.status_text = dpg.add_text("Ready", parent=parent, color=(180, 180, 180))
        self.summary_text = dpg.add_text(
            "No disc source is open.", parent=parent, wrap=1050
        )
        self.loading = dpg.add_loading_indicator(
            parent=parent,
            radius=2.5,
            style=1,
            show=False,
        )
        dpg.add_spacer(height=4, parent=parent)

        with dpg.child_window(parent=parent, height=-120, border=True):
            self.table = dpg.add_table(
                header_row=True,
                resizable=True,
                policy=dpg.mvTable_SizingStretchProp,
                row_background=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
            )
            dpg.add_table_column(label="Path", init_width_or_weight=5.0, parent=self.table)
            dpg.add_table_column(label="Type", init_width_or_weight=0.8, parent=self.table)
            dpg.add_table_column(label="LBA", init_width_or_weight=1.0, parent=self.table)
            dpg.add_table_column(label="Size", init_width_or_weight=1.2, parent=self.table)

        dpg.add_separator(parent=parent)
        self.selection_text = dpg.add_text(
            "Selected: [ None ]",
            parent=parent,
            color=(150, 190, 255),
        )
        dpg.add_text(
            "Disc-writing and SAROO capture actions will use the same worker/event boundary as this scanner as they are added.",
            parent=parent,
            wrap=1050,
            color=(140, 140, 140),
        )

        with dpg.file_dialog(
            directory_selector=False,
            show=False,
            modal=True,
            callback=self._source_dialog_selected,
            tag="srk_source_file_dialog",
            width=760,
            height=520,
        ) as self.source_dialog:
            dpg.add_file_extension(".cue")
            dpg.add_file_extension(".iso")
            dpg.add_file_extension(".bin")
            dpg.add_file_extension(".img")
            dpg.add_file_extension(".raw")
            dpg.add_file_extension(".*")

        with dpg.file_dialog(
            directory_selector=True,
            show=False,
            modal=True,
            callback=self._output_dialog_selected,
            tag="srk_output_directory_dialog",
            width=760,
            height=520,
        ) as self.output_dialog:
            pass

    def show_source_dialog(self) -> None:
        if self._built:
            dpg.show_item(self.source_dialog)

    def _source_dialog_selected(self, sender=None, app_data=None, user_data=None) -> None:
        del sender, user_data
        path = self._dialog_selection(app_data)
        if path:
            dpg.set_value(self.source_input, path)

    def _output_dialog_selected(self, sender=None, app_data=None, user_data=None) -> None:
        del sender, user_data
        path = self._dialog_selection(app_data)
        if path:
            self.output_dir = path
            dpg.set_value(self.output_input, path)

    def _open_source(self, sender=None, app_data=None, user_data=None) -> None:
        del sender, app_data, user_data
        if self.controller.is_busy:
            return
        path = str(dpg.get_value(self.source_input) or "").strip()
        if not path:
            dpg.set_value(self.status_text, "Choose a disc image first.")
            dpg.configure_item(self.status_text, color=(255, 180, 80))
            return
        try:
            self.controller.open_source(path)
        except Exception as exc:
            dpg.set_value(self.status_text, f"{type(exc).__name__}: {exc}")
            dpg.configure_item(self.status_text, color=(255, 110, 110))

    def _set_busy(self, busy: bool) -> None:
        dpg.configure_item(self.open_button, enabled=not busy)
        dpg.configure_item(self.loading, show=busy)

    def _clear_table(self) -> None:
        for row in self._table_rows:
            if dpg.does_item_exist(row):
                dpg.delete_item(row)
        self._table_rows.clear()

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KiB"
        return f"{size / (1024 * 1024):.2f} MiB"

    def _select_entry(self, sender=None, app_data=None, user_data=None) -> None:
        del sender, app_data
        entry = user_data
        if not isinstance(entry, DiscEntrySnapshot):
            return
        self._selected_entry = entry
        kind = "DIR" if entry.is_dir else "FILE"
        dpg.set_value(
            self.selection_text,
            f"Selected: {entry.path} | {kind} | LBA 0x{entry.lba:08X} | {entry.size:,} bytes",
        )

    def _populate(self, snapshot: DiscWorkspaceSnapshot) -> None:
        self._clear_table()
        for index, entry in enumerate(snapshot.entries):
            row_tag = f"srk_disc_row_{index}_{id(self)}"
            with dpg.table_row(parent=self.table, tag=row_tag):
                dpg.add_selectable(
                    label=entry.path,
                    callback=self._select_entry,
                    user_data=entry,
                )
                dpg.add_text("DIR" if entry.is_dir else "FILE")
                dpg.add_text(f"0x{entry.lba:08X}")
                dpg.add_text(self._format_size(entry.size))
            self._table_rows.append(row_tag)

    def _on_controller_event(self, event: DiscControllerEvent) -> None:
        # Worker events are dispatched by BackgroundWorkerService.update(),
        # which GuiEngine invokes on the Dear PyGui owner thread.
        if not self._built:
            return
        if event.kind == "opening":
            self._set_busy(True)
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(150, 190, 255))
            return

        self._set_busy(False)
        if event.kind == "opened" and event.snapshot is not None:
            self._snapshot = event.snapshot
            self._selected_entry = None
            self._populate(event.snapshot)
            dpg.set_value(self.status_text, "Disc opened read-only.")
            dpg.configure_item(self.status_text, color=(80, 220, 160))
            dpg.set_value(
                self.summary_text,
                (
                    f"{event.snapshot.source_kind} | "
                    f"{event.snapshot.file_count} file(s) | "
                    f"{event.snapshot.directory_count} directories | "
                    f"{event.snapshot.source_path}"
                ),
            )
            dpg.set_value(self.selection_text, "Selected: [ None ]")
        elif event.kind == "error":
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(255, 110, 110))
        elif event.kind == "cancelled":
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(255, 180, 80))
        elif event.kind == "closed":
            self._snapshot = None
            self._selected_entry = None
            self._clear_table()
            dpg.set_value(self.status_text, "Disc source closed.")
            dpg.set_value(self.summary_text, "No disc source is open.")
            dpg.set_value(self.selection_text, "Selected: [ None ]")

    def on_show(self, **kwargs: object) -> None:
        del kwargs

    def update(self, delta_seconds: float) -> None:
        del delta_seconds
        if self._pending_initial_source and not self.controller.is_busy:
            source = self._pending_initial_source
            self._pending_initial_source = None
            dpg.set_value(self.source_input, source)
            self._open_source()
