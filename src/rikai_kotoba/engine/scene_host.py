"""Dear PyGui adapter for the backend-neutral scene registry."""

from __future__ import annotations

import dearpygui.dearpygui as dpg


class DearPyGuiSceneHost:
    def exists(self, container: object) -> bool:
        try:
            return bool(dpg.does_item_exist(container))
        except Exception:
            return False

    def show(self, container: object) -> None:
        dpg.configure_item(container, show=True)

    def hide(self, container: object) -> None:
        dpg.configure_item(container, show=False)
