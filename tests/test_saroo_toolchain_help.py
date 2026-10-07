from __future__ import annotations

import unittest

from rikai_kotoba.application import help_catalog


class SarooToolchainHelpTests(unittest.TestCase):
    def test_toolchain_glossary_terms_are_available(self) -> None:
        for term in ("Toolchain", "Cross-compiler", "Makefile", "SaturnOrbit"):
            with self.subTest(term=term):
                self.assertIsNotNone(help_catalog.glossary_entry(term))

    def test_toolchain_command_is_searchable_offline(self) -> None:
        results = help_catalog.search("srk-saroo-toolchain")
        self.assertIn(
            ("page:saroo-capture", "SAROO memory capture and SD-card exchange"),
            results,
        )

    def test_preflight_safety_language_is_searchable(self) -> None:
        results = help_catalog.search("PATH is not modified")
        self.assertTrue(any(target == "page:saroo-capture" for target, _ in results))


if __name__ == "__main__":
    unittest.main()
