"""Salix responsive-layout composition and compatibility surface.

Reusable callback coordination and low-churn geometry application live in
:mod:`salix.framework.responsive`. Dear PyGui resize hooks and item operations
live in :mod:`salix.engine.layout_hosts.dearpygui`.
"""

from __future__ import annotations

from salix.engine.layout_hosts import DearPyGuiLayoutHost
from salix.framework.geometry import (
    ContentBounds,
    ContentMetrics,
    DialogMetrics,
    HorizontalAlign,
    Number,
    VerticalAlign,
    aligned_offset,
    clamp,
    content_bounds,
    fill_height,
    split_widths,
)
from salix.framework.responsive import LayoutCoordinator


class ResponsiveLayout(LayoutCoordinator):
    """Application singleton backed by the concrete Dear PyGui layout host."""

    _instance: "ResponsiveLayout | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__(DearPyGuiLayoutHost())
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "ResponsiveLayout":
        return cls()


__all__ = [
    "ContentBounds",
    "ContentMetrics",
    "DialogMetrics",
    "HorizontalAlign",
    "Number",
    "ResponsiveLayout",
    "VerticalAlign",
    "aligned_offset",
    "clamp",
    "content_bounds",
    "fill_height",
    "split_widths",
]
