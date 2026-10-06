"""Tests proving Mjolnir does not depend on repository-local image paths."""

import os
import tempfile
import unittest

from rikai_kotoba.tools.mjolnir import (
    _resolve_startup_source,
    _structured_output_root,
    _portable_zip_output_path,
)


class MjolnirPathTests(unittest.TestCase):
    def test_directory_argument_becomes_image_search_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            search_root, session = _resolve_startup_source(temp_dir)

            self.assertEqual(search_root, os.path.abspath(temp_dir))
            self.assertIsNone(session)

    def test_no_source_uses_current_working_directory_not_repo_iso(self):
        original = os.getcwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                search_root, session = _resolve_startup_source(None)
            finally:
                os.chdir(original)

            self.assertEqual(search_root, os.path.abspath(temp_dir))
            self.assertIsNone(session)

    def test_output_helpers_are_rooted_in_user_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            structured = _structured_output_root(temp_dir, "Example Disc")
            portable = _portable_zip_output_path(temp_dir, "Example Disc")

            self.assertEqual(
                structured,
                os.path.join(temp_dir, "extracted_output", "Example Disc"),
            )
            self.assertEqual(
                portable,
                os.path.join(
                    temp_dir,
                    "extracted_output",
                    "Example Disc-dump.zip",
                ),
            )


if __name__ == "__main__":
    unittest.main()
