"""Reusable backend-neutral Salix component foundations."""

from .base import Component, ValueComponent
from .bindings import BindingSet, ValueBinding
from .controls import (
    Button,
    CheckBox,
    ComboBox,
    Label,
    NumericKind,
    NumericStepper,
    ProgressBar,
    Separator,
    Spacer,
    TextInput,
)
from .events import ComponentEvent, ComponentEventType, action_callback
from .layout import (
    AUTO,
    FILL,
    NATURAL,
    STRETCH,
    ControlLayout,
    ControlLayoutDefaults,
    ControlLayoutTheme,
    CrossAxisMode,
    DimensionMode,
    ResolvedControlLayout,
    backend_dimension,
    cross_axis_mode,
    resolve_control_layout,
)
from .profile import ComponentLayoutProfile, FRAMEWORK_COMPONENT_PROFILE
from .renderer import (
    ComponentRenderer,
    clear_default_renderer,
    get_default_renderer,
    set_default_renderer,
)
from .state import ComponentGroup

__all__ = [
    "AUTO",
    "FILL",
    "NATURAL",
    "STRETCH",
    "BindingSet",
    "Button",
    "CheckBox",
    "ComboBox",
    "Component",
    "ComponentEvent",
    "ComponentEventType",
    "ComponentGroup",
    "ComponentLayoutProfile",
    "ComponentRenderer",
    "ControlLayout",
    "ControlLayoutDefaults",
    "ControlLayoutTheme",
    "CrossAxisMode",
    "DimensionMode",
    "FRAMEWORK_COMPONENT_PROFILE",
    "Label",
    "NumericKind",
    "NumericStepper",
    "ProgressBar",
    "ResolvedControlLayout",
    "Separator",
    "Spacer",
    "TextInput",
    "ValueBinding",
    "ValueComponent",
    "action_callback",
    "backend_dimension",
    "clear_default_renderer",
    "cross_axis_mode",
    "get_default_renderer",
    "resolve_control_layout",
    "set_default_renderer",
]
