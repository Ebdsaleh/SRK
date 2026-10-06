"""Tests for the Dear PyGui desktop entry-point parser without importing DPG."""

import unittest

from rikai_kotoba.desktop import build_argument_parser


class DesktopEntryTests(unittest.TestCase):
    def test_desktop_accepts_optional_source_and_output_workspace(self):
        parser = build_argument_parser()
        args = parser.parse_args(["sample.cue", "--output-dir", "workspace"])
        self.assertEqual(args.source, "sample.cue")
        self.assertEqual(args.output_dir, "workspace")

    def test_desktop_source_is_optional(self):
        parser = build_argument_parser()
        args = parser.parse_args([])
        self.assertIsNone(args.source)
        self.assertIsNone(args.output_dir)


if __name__ == "__main__":
    unittest.main()
