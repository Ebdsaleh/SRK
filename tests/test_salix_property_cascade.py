from __future__ import annotations

import unittest

from salix.framework.property_cascade import (
    PropertySource,
    UNSET,
    is_unset,
    resolve_property,
)


class SalixPropertyCascadeTests(unittest.TestCase):
    def test_default_is_used_when_theme_and_instance_are_unset(self):
        result = resolve_property(default=10, theme=UNSET, override=UNSET)
        self.assertEqual(result.value, 10)
        self.assertEqual(result.source, PropertySource.DEFAULT)
        self.assertEqual(result.rejected, ())

    def test_instance_override_has_highest_precedence(self):
        result = resolve_property(default=10, theme=20, override=30)
        self.assertEqual(result.value, 30)
        self.assertEqual(result.source, PropertySource.INSTANCE)

    def test_invalid_instance_falls_back_to_valid_theme(self):
        result = resolve_property(
            default=10,
            theme=20,
            override=-1,
            validator=lambda value: isinstance(value, int) and value > 0,
        )
        self.assertEqual(result.value, 20)
        self.assertEqual(result.source, PropertySource.THEME)
        self.assertEqual(len(result.rejected), 1)
        self.assertEqual(result.rejected[0].source, PropertySource.INSTANCE)

    def test_none_can_be_an_explicit_value(self):
        result = resolve_property(
            default=5,
            override=None,
            validator=lambda value: value is None or isinstance(value, int),
        )
        self.assertIsNone(result.value)
        self.assertEqual(result.source, PropertySource.INSTANCE)

    def test_invalid_framework_default_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_property(
                default=-1,
                validator=lambda value: isinstance(value, int) and value > 0,
            )

    def test_unset_sentinel_is_falsey_and_detectable(self):
        self.assertTrue(is_unset(UNSET))
        self.assertFalse(bool(UNSET))
        self.assertEqual(repr(UNSET), "UNSET")


if __name__ == "__main__":
    unittest.main()
