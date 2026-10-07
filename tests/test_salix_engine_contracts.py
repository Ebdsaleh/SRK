"""Headless contract tests for Salix Dear PyGui adapter composition."""

from __future__ import annotations

import unittest

from salix.engine.component_renderers import DearPyGuiRenderer
from salix.engine.layout_hosts import DearPyGuiLayoutHost
from salix.engine.presentation_backends import create_dearpygui_backend
from salix.framework.components import ComponentEventType
from salix.runtime.presentation import PresentationCapability


class SalixEngineContractTests(unittest.TestCase):
    def test_backend_composition_advertises_extracted_capabilities(self):
        backend = create_dearpygui_backend()
        self.assertEqual(backend.name, "dearpygui")
        self.assertTrue(backend.supports(PresentationCapability.COMPONENTS))
        self.assertTrue(backend.supports(PresentationCapability.RESPONSIVE_LAYOUT))
        self.assertTrue(backend.supports(PresentationCapability.SCENES))
        self.assertTrue(backend.supports(PresentationCapability.COMMAND_MENUS))

    def test_component_event_adapter_is_semantic_without_toolkit_context(self):
        renderer = DearPyGuiRenderer()
        received = []
        source = object()
        callback = renderer.event_callback(
            source,
            ComponentEventType.CHANGE,
            received.append,
            data={"field": "example"},
        )
        callback("native-sender", "new-value", None)
        self.assertEqual(len(received), 1)
        self.assertIs(received[0].source, source)
        self.assertEqual(received[0].event_type, ComponentEventType.CHANGE)
        self.assertEqual(received[0].value, "new-value")
        self.assertEqual(received[0].data, {"field": "example"})

    def test_layout_host_callback_adapter_discards_native_arguments(self):
        calls = []
        callback = DearPyGuiLayoutHost._backend_callback(lambda: calls.append("called"))
        callback("sender", {"width": 800}, "data")
        self.assertEqual(calls, ["called"])


if __name__ == "__main__":
    unittest.main()
