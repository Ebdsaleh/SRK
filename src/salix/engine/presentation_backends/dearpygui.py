"""Dear PyGui presentation-backend composition for the Salix core surface."""

from __future__ import annotations

from salix.engine.component_renderers import DearPyGuiRenderer
from salix.engine.layout_hosts import DearPyGuiLayoutHost
from salix.engine.scene_hosts import DearPyGuiSceneHost
from salix.framework.components.profile import ComponentLayoutProfile
from salix.runtime.presentation import PresentationBackend


def create_dearpygui_backend(
    *, component_profile: ComponentLayoutProfile | None = None
) -> PresentationBackend:
    """Compose the currently extracted Dear PyGui adapters as one bundle."""

    return PresentationBackend(
        "dearpygui",
        component_renderer=DearPyGuiRenderer(component_profile=component_profile),
        layout_host=DearPyGuiLayoutHost(),
        scene_host=DearPyGuiSceneHost(),
    )
