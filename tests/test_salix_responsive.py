from __future__ import annotations

import unittest

from salix.framework.geometry import DialogMetrics
from salix.framework.responsive import LayoutCoordinator


class _FakeLayoutHost:
    def __init__(self):
        self.viewport_callback = None
        self.watches = {}
        self.sizes = {}
        self.configured = []

    def install_viewport_resize(self, callback):
        self.viewport_callback = callback
        return True

    def watch_item_resize(self, item, callback):
        token = (item, len(self.watches))
        self.watches[token] = callback
        return token

    def unwatch_item_resize(self, watch):
        self.watches.pop(watch, None)

    def item_size(self, item):
        return self.sizes.get(item, (0, 0))

    def configure(self, item, **kwargs):
        self.configured.append((item, kwargs))
        return True


class SalixResponsiveTests(unittest.TestCase):
    def test_viewport_callback_is_installed_once(self):
        host = _FakeLayoutHost()
        layout = LayoutCoordinator(host)
        self.assertTrue(layout.install_viewport_callback())
        self.assertFalse(layout.install_viewport_callback())

    def test_registered_viewport_callback_is_dispatched(self):
        host = _FakeLayoutHost()
        layout = LayoutCoordinator(host)
        calls = []
        layout.register_viewport("main", lambda: calls.append("called"))
        layout.install_viewport_callback()
        host.viewport_callback()
        self.assertEqual(calls, ["called"])

    def test_repeated_geometry_is_not_reapplied(self):
        host = _FakeLayoutHost()
        layout = LayoutCoordinator(host)
        self.assertTrue(layout.width("panel", 320))
        self.assertFalse(layout.width("panel", 320))
        self.assertEqual(len(host.configured), 1)

    def test_item_watch_triggers_registered_callback(self):
        host = _FakeLayoutHost()
        layout = LayoutCoordinator(host)
        calls = []
        token = layout.watch_item("panel", "panel-layout", lambda: calls.append(1))
        host.watches[token]()
        self.assertEqual(calls, [1])

    def test_dialog_applies_content_height_and_wrap(self):
        host = _FakeLayoutHost()
        host.sizes["dialog"] = (800, 600)
        layout = LayoutCoordinator(host)
        layout.dialog(
            "dialog",
            "content",
            metrics=DialogMetrics(reserved_height=100),
            wrap_items=("body",),
        )
        self.assertIn(("content", {"height": 500}), host.configured)
        self.assertIn(("body", {"wrap": 752}), host.configured)

    def test_callback_failure_is_isolated(self):
        host = _FakeLayoutHost()
        layout = LayoutCoordinator(host)

        def broken():
            raise RuntimeError("boom")

        layout.register_viewport("broken", broken)
        self.assertFalse(layout.trigger("broken"))


if __name__ == "__main__":
    unittest.main()
