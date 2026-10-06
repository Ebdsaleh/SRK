"""Initial SAROO hardware-tool scene."""

from __future__ import annotations

import dearpygui.dearpygui as dpg


class SarooView:
    """Presentation shell reserved for generic Saturn/SAROO runtime tooling."""

    def build(self, parent: str | int) -> None:
        dpg.add_text("SATURN / SAROO", parent=parent, color=(255, 190, 90))
        dpg.add_text(
            "Original-hardware flight-recorder and runtime-provenance tools will live here. The public SRK layer will operate on addresses, ranges, dumps, and capture sessions without title-specific constants.",
            parent=parent,
            wrap=1050,
            color=(180, 180, 180),
        )
        dpg.add_spacer(height=10, parent=parent)
        dpg.add_text("Transport status: Not implemented yet", parent=parent)
        dpg.add_text("Capture destination: SRK workspace / Dumps / SAROO", parent=parent)
        dpg.add_spacer(height=8, parent=parent)

        with dpg.group(horizontal=True, parent=parent):
            dpg.add_button(label="Refresh Device", enabled=False)
            dpg.add_button(label="Capture Work RAM-L", enabled=False)
            dpg.add_button(label="Capture Work RAM-H", enabled=False)
            dpg.add_button(label="Capture Both", enabled=False)

        dpg.add_separator(parent=parent)
        dpg.add_text("Planned generic pipeline", parent=parent, color=(150, 190, 255))
        for line in (
            "1. Detect / communicate with SAROO-side capture helper",
            "2. Request deterministic Saturn RAM snapshots",
            "3. Persist dumps outside the Git repository",
            "4. Correlate disc extents against captured memory",
            "5. Prove runtime execution before patching hooks",
        ):
            dpg.add_text(line, parent=parent)

    def update(self, delta_seconds: float) -> None:
        del delta_seconds
