from __future__ import annotations

import contextlib
import unittest

from salix.framework.components import (
    BindingSet,
    ComponentGroup,
    ComponentLayoutProfile,
    ControlLayout,
    ControlLayoutDefaults,
    ValueBinding,
    ValueComponent,
    clear_default_renderer,
    set_default_renderer,
)


class _FakeRenderer:
    def __init__(self):
        self.component_profile = ComponentLayoutProfile(
            layouts={"component": ControlLayoutDefaults(width=90, height=30)}
        )
        self.values = {}
        self.configured = []
        self.destroyed = []

    def set_component_profile(self, profile):
        self.component_profile = profile

    def create(self, kind, **kwargs):
        item = f"{kind}:{len(self.values)}"
        self.values[item] = kwargs.get("default_value")
        return item

    @contextlib.contextmanager
    def container(self, kind, **kwargs):
        yield self.create(kind, **kwargs)

    def get_value(self, item):
        return self.values[item]

    def set_value(self, item, value):
        self.values[item] = value

    def configure(self, item, **kwargs):
        self.configured.append((item, kwargs))

    def place(self, item, x, y):
        self.configured.append((item, {"pos": (x, y)}))

    def measure(self, item):
        return (90, 30)

    def exists(self, item):
        return item in self.values and item not in self.destroyed

    def destroy(self, item):
        self.destroyed.append(item)

    def event_callback(self, source, event_type, callback, *, data=None):
        return callback

    def center(self, item, *, fallback_size=None):
        return None

    def attach_tooltip(self, item, text, *, wrap=450):
        return None


class _Value(ValueComponent):
    def __init__(self, value=None, **kwargs):
        super().__init__(**kwargs)
        self.initial_value = value

    def build(self, *, renderer=None, parent=None):
        active = renderer or self._renderer
        if active is None:
            from salix.framework.components import get_default_renderer

            active = get_default_renderer()
        resolved = self._resolve_layout(renderer=active)
        kwargs = self._layout_kwargs(resolved)
        kwargs["default_value"] = self.initial_value
        if parent is not None:
            kwargs["parent"] = parent
        return self._bind(active, active.create("input_text", **kwargs))


class SalixComponentCoreTests(unittest.TestCase):
    def setUp(self):
        clear_default_renderer()
        self.renderer = _FakeRenderer()
        set_default_renderer(self.renderer)

    def tearDown(self):
        clear_default_renderer(self.renderer)

    def test_component_resolves_profile_then_instance_layout(self):
        component = _Value("hello", layout=ControlLayout(width=120))
        component.build()
        self.assertEqual(component.resolved_layout.width, 120)
        self.assertEqual(component.resolved_layout.height, 30)

    def test_value_component_reads_and_writes_through_renderer(self):
        component = _Value("before")
        component.build()
        self.assertEqual(component.get_value(), "before")
        component.set_value("after")
        self.assertEqual(component.get_value(), "after")

    def test_component_group_applies_runtime_state(self):
        one = _Value("one")
        two = _Value("two")
        one.build()
        two.build()
        group = ComponentGroup(one, two)
        group.set_enabled(False)
        group.set_visible(False)
        self.assertEqual(len(self.renderer.configured), 4)

    def test_binding_set_collects_and_applies_explicitly(self):
        name = _Value("Ada")
        count = _Value("3")
        name.build()
        count.build()
        bindings = BindingSet(
            ValueBinding("name", name),
            ValueBinding("count", count, read_transform=int, write_transform=str),
        )
        self.assertEqual(bindings.collect(), {"name": "Ada", "count": 3})
        self.assertEqual(bindings.apply({"name": "Grace", "count": 7}), ("name", "count"))
        self.assertEqual(name.get_value(), "Grace")
        self.assertEqual(count.get_value(), "7")

    def test_dispose_invalidates_backend_item(self):
        component = _Value("x")
        item = component.build()
        self.assertTrue(component.exists())
        self.assertTrue(component.dispose())
        self.assertIn(item, self.renderer.destroyed)
        self.assertFalse(component.exists())


if __name__ == "__main__":
    unittest.main()
