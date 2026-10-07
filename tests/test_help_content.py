from __future__ import annotations

import unittest

from rikai_kotoba.application.help_content import (
    GLOSSARY,
    PAGE_ORDER,
    PAGES,
    contextual_help,
    glossary_entry,
    glossary_for_letter,
    glossary_letters,
    glossary_page,
    page,
    search,
)


class HelpContentTests(unittest.TestCase):
    def test_page_order_resolves_to_real_pages(self):
        self.assertTrue(PAGE_ORDER)
        self.assertTrue(all(key in PAGES for key in PAGE_ORDER))
        self.assertEqual(page("welcome").title, "SRK Offline Manual")

    def test_glossary_terms_are_unique_case_insensitively(self):
        terms = [entry.term.casefold() for entry in GLOSSARY]
        self.assertEqual(len(terms), len(set(terms)))

    def test_glossary_alias_lookup_is_case_insensitive(self):
        entry = glossary_entry("logical block address")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.term, "LBA")

    def test_glossary_a_to_z_navigation_is_generated_from_content(self):
        letters = glossary_letters()
        self.assertIn("C", letters)
        entries = glossary_for_letter("c")
        self.assertTrue(any(entry.term == "CUE" for entry in entries))
        self.assertTrue(any(entry.term == "Correlation" for entry in entries))

    def test_contextual_help_uses_same_glossary_definition(self):
        entry = glossary_entry("SAROO")
        rendered = contextual_help("saroo")
        self.assertIn(entry.definition, rendered)
        self.assertIn("Related:", rendered)

    def test_search_covers_pages_and_glossary(self):
        results = search("logical block")
        self.assertTrue(any(key.startswith("glossary:LBA") for key, _label in results))
        disc_results = search("audio track")
        self.assertTrue(any(key == "page:disc-images" for key, _label in disc_results))

    def test_glossary_page_is_semantic_document(self):
        document = glossary_page("L")
        self.assertEqual(document.title, "Glossary — L")
        self.assertTrue(any(section.title == "LBA" for section in document.sections))

    def test_source_image_policy_is_present_in_offline_manual(self):
        document = page("welcome")
        rendered = "\n".join(
            block.body
            for section in document.sections
            for block in section.blocks
            if hasattr(block, "body")
        )
        self.assertIn("never modify", rendered.lower())


if __name__ == "__main__":
    unittest.main()
