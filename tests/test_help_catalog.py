"""Tests for the composed offline SRK manual and glossary catalog."""

import unittest

from rikai_kotoba.application import help_catalog


class HelpCatalogTests(unittest.TestCase):
    def test_saroo_capture_page_is_in_contents_catalog(self):
        self.assertIn("saroo-capture", help_catalog.PAGE_ORDER)
        page = help_catalog.page("saroo-capture")
        self.assertIsNotNone(page)
        self.assertIn("SAROO", page.title)

    def test_saroo_capture_terms_join_global_glossary(self):
        entry = help_catalog.glossary_entry("transport adapter")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.term, "Transport adapter")
        self.assertIs(help_catalog.glossary_entry("SHA256"), help_catalog.glossary_entry("SHA-256"))

    def test_search_reaches_modular_saroo_manual(self):
        results = help_catalog.search("64 KiB")
        self.assertIn(
            ("page:saroo-capture", "SAROO memory capture and SD-card exchange"),
            results,
        )

    def test_glossary_letters_include_new_terms_without_duplicates(self):
        letters = help_catalog.glossary_letters()
        self.assertEqual(len(letters), len(set(letters)))
        self.assertIn("T", letters)
        terms = [entry.term.casefold() for entry in help_catalog.GLOSSARY]
        self.assertEqual(len(terms), len(set(terms)))


if __name__ == "__main__":
    unittest.main()
