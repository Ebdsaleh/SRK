"""SAROO original-hardware capture scene."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from rikai_kotoba.application.saroo_capture import (
    SarooCaptureController,
    SarooControllerEvent,
)
from rikai_kotoba.hardware.saturn.memory_map import WORK_RAM_HIGH, WORK_RAM_LOW
from rikai_kotoba.hardware.saturn.saroo import MemoryRange


class SarooView:
    """Presentation for title-neutral Saturn/SAROO capture workflows."""

    def __init__(self, controller: SarooCaptureController) -> None:
        if not isinstance(controller, SarooCaptureController):
            raise TypeError("SarooView requires a SarooCaptureController")
        self.controller = controller
        self._built = False
        self._pending_refresh = True
        self._transport_available = False
        self._capture_buttons: list[object] = []
        controller.subscribe(self._on_controller_event)

    @staticmethod
    def _capture_range(region) -> MemoryRange:
        return MemoryRange(
            region.start_address,
            region.size,
            region.name.lower().replace(" ", "_"),
        )

    @staticmethod
    def _range_text(region) -> str:
        end = region.end_address_exclusive - 1
        return (
            f"{region.name}: 0x{region.start_address:08X}-0x{end:08X} "
            f"({region.size // (1024 * 1024)} MiB)"
        )

    def build(self, parent: str | int) -> None:
        self._built = True
        dpg.add_text("SATURN / SAROO", parent=parent, color=(255, 190, 90))
        dpg.add_text(
            "Original-hardware flight-recorder and runtime-provenance tools operate on caller-selected addresses, ranges, dumps, and capture sessions without title-specific constants.",
            parent=parent,
            wrap=1050,
            color=(180, 180, 180),
        )
        dpg.add_spacer(height=8, parent=parent)

        self.transport_text = dpg.add_text(
            "Transport: waiting for status check...",
            parent=parent,
            color=(255, 190, 90),
        )
        dpg.add_text(
            f"Capture destination: {self.controller.capture_root}",
            parent=parent,
            wrap=1050,
        )
        dpg.add_text(self._range_text(WORK_RAM_LOW), parent=parent)
        dpg.add_text(self._range_text(WORK_RAM_HIGH), parent=parent)
        dpg.add_spacer(height=8, parent=parent)

        dpg.add_text("Checkpoint label", parent=parent)
        self.checkpoint_input = dpg.add_input_text(
            default_value="manual-checkpoint",
            width=420,
            parent=parent,
        )
        dpg.add_text("Session label (optional)", parent=parent)
        self.session_input = dpg.add_input_text(
            default_value="",
            width=420,
            parent=parent,
        )
        dpg.add_spacer(height=6, parent=parent)

        with dpg.group(horizontal=True, parent=parent):
            self.refresh_button = dpg.add_button(
                label="Refresh Device",
                callback=lambda *_args: self._refresh_status(),
            )
            self._capture_buttons = [
                dpg.add_button(
                    label="Capture Work RAM-L",
                    enabled=False,
                    callback=lambda *_args: self._capture((WORK_RAM_LOW,)),
                ),
                dpg.add_button(
                    label="Capture Work RAM-H",
                    enabled=False,
                    callback=lambda *_args: self._capture((WORK_RAM_HIGH,)),
                ),
                dpg.add_button(
                    label="Capture Both",
                    enabled=False,
                    callback=lambda *_args: self._capture((WORK_RAM_LOW, WORK_RAM_HIGH)),
                ),
            ]

        self.status_text = dpg.add_text(
            "Ready to check for a configured transport.",
            parent=parent,
            color=(180, 180, 180),
            wrap=1050,
        )
        dpg.add_separator(parent=parent)
        dpg.add_text("Evidence pipeline", parent=parent, color=(150, 190, 255))
        for line in (
            "1. Ask a verified transport for explicit Saturn memory ranges",
            "2. Save immutable region files plus SHA-256 capture.json metadata",
            "3. Keep captures under the external SRK-Workspace/Dumps/SAROO tree",
            "4. Correlate extracted disc files against captured memory",
            "5. Prove runtime provenance before introducing title-specific hooks",
        ):
            dpg.add_text(line, parent=parent)

        dpg.add_spacer(height=8, parent=parent)
        dpg.add_text(
            "Current transport policy: SRK will not guess a SAROO communication protocol. Capture buttons enable only when a verified adapter reports that it is available.",
            parent=parent,
            wrap=1050,
            color=(140, 140, 140),
        )

    def _set_busy(self, busy: bool) -> None:
        if not self._built:
            return
        dpg.configure_item(self.refresh_button, enabled=not busy)
        enable_capture = self._transport_available and not busy
        for button in self._capture_buttons:
            dpg.configure_item(button, enabled=enable_capture)

    def _refresh_status(self) -> None:
        if self.controller.is_busy:
            return
        try:
            self.controller.refresh_status()
        except Exception as exc:
            dpg.set_value(self.status_text, f"{type(exc).__name__}: {exc}")
            dpg.configure_item(self.status_text, color=(255, 110, 110))

    def _capture(self, regions) -> None:
        if self.controller.is_busy or not self._transport_available:
            return
        checkpoint = str(dpg.get_value(self.checkpoint_input) or "").strip()
        session_label = str(dpg.get_value(self.session_input) or "").strip()
        try:
            self.controller.capture(
                checkpoint,
                tuple(self._capture_range(region) for region in regions),
                session_label=session_label,
            )
        except Exception as exc:
            dpg.set_value(self.status_text, f"{type(exc).__name__}: {exc}")
            dpg.configure_item(self.status_text, color=(255, 110, 110))

    def _on_controller_event(self, event: SarooControllerEvent) -> None:
        if not self._built:
            return
        if event.kind in {"checking", "capturing"}:
            self._set_busy(True)
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(150, 190, 255))
            return

        self._set_busy(False)
        if event.kind == "status" and event.status is not None:
            self._transport_available = event.status.available
            state = "available" if event.status.available else "unavailable"
            detail = f" - {event.status.detail}" if event.status.detail else ""
            dpg.set_value(
                self.transport_text,
                f"Transport: {event.status.name} ({state}){detail}",
            )
            dpg.configure_item(
                self.transport_text,
                color=(80, 220, 160) if event.status.available else (255, 190, 90),
            )
            self._set_busy(False)
            dpg.set_value(
                self.status_text,
                "Transport ready." if event.status.available else "No verified SAROO transport is configured yet.",
            )
            dpg.configure_item(
                self.status_text,
                color=(80, 220, 160) if event.status.available else (180, 180, 180),
            )
        elif event.kind == "captured" and event.artifact is not None:
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(80, 220, 160))
        elif event.kind == "cancelled":
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(255, 190, 90))
        elif event.kind == "error":
            dpg.set_value(self.status_text, event.message)
            dpg.configure_item(self.status_text, color=(255, 110, 110))

    def update(self, delta_seconds: float) -> None:
        del delta_seconds
        if self._pending_refresh and not self.controller.is_busy:
            self._pending_refresh = False
            self._refresh_status()
