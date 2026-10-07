"""Regression tests for Dear PyGui Help navigation callback routing."""

import unittest

from rikai_kotoba.views.help import HelpView


class HelpViewCallbackTests(unittest.TestCase):
    def setUp(self):
        self.view = HelpView(object())
        self.calls = []

        self.view.open_page = lambda key: self.calls.append(("page", key)) or True
        self.view.open_glossary_letter = lambda letter: self.calls.append(
            ("letter", letter)
        )
        self.view.open_glossary_term = lambda term: self.calls.append(
            ("term", term)
        ) or True

    def test_contents_callback_uses_explicit_user_data(self):
        self.view._page_button_clicked("sender", None, "mjolnir")

        self.assertEqual(self.calls, [("page", "mjolnir")])

    def test_glossary_letter_callback_uses_explicit_user_data(self):
        self.view._glossary_letter_clicked("sender", None, "S")

        self.assertEqual(self.calls, [("letter", "S")])

    def test_search_result_callback_routes_page_and_glossary_targets(self):
        self.view._search_result_clicked("sender", None, "page:saroo-capture")
        self.view._search_result_clicked("sender", None, "glossary:SHA-256")

        self.assertEqual(
            self.calls,
            [("page", "saroo-capture"), ("term", "SHA-256")],
        )

    def test_missing_user_data_is_ignored_instead_of_throwing(self):
        self.view._page_button_clicked("sender", None, None)
        self.view._glossary_letter_clicked("sender", None, None)
        self.view._search_result_clicked("sender", None, None)

        self.assertEqual(self.calls, [])
        self.assertFalse(self.view._open_search_result(None))

    def test_unknown_search_target_is_rejected_without_dispatch(self):
        self.assertFalse(self.view._open_search_result("unknown:target"))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
