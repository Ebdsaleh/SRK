"""Regression coverage for generated SAROO C whitespace."""

import unittest

from rikai_kotoba.hardware.saturn.saroo.ingame_entry_integration import (
    _MAIN_HANDLER_PATCH,
)


class SarooInGameGeneratedCWhitespaceTests(unittest.TestCase):
    def test_handler_patch_uses_real_whitespace_not_literal_tab_escape_text(self):
        self.assertIn("\t}else if(index==srk_first_read_index){", _MAIN_HANDLER_PATCH)
        self.assertNotIn(r"\t}else if(index==srk_first_read_index){", _MAIN_HANDLER_PATCH)
        self.assertNotIn(r"\t\tint retv;", _MAIN_HANDLER_PATCH)


if __name__ == "__main__":
    unittest.main()
