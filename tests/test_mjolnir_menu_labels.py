"""Tests for Mjolnir's state-aware menu labels."""

import unittest

from rikai_kotoba.core.iso9660 import ISO9660Entry
from rikai_kotoba.tools.mjolnir import DiscSession, _menu_option_lines


class MjolnirMenuLabelTests(unittest.TestCase):
    def test_no_selection_uses_generic_placeholders(self):
        lines = _menu_option_lines(None, None)

        self.assertIn(
            "4. Dump active file to hex file (<filename>.hex)",
            lines,
        )
        self.assertIn(
            "5. Dump filesystem to one hex blob (<imagefilename>.hex)",
            lines,
        )
        self.assertIn(
            "6. Structured image dump (extracted_output/<image>/)",
            lines,
        )
        self.assertIn(
            "7. Portable structured dump (extracted_output/<image>-dump.zip)",
            lines,
        )

    def test_selected_image_previews_real_image_outputs(self):
        session = DiscSession(
            source_path=r"C:\images\Example Game (Disc 1).cue",
            source=object(),
            reader=None,
            extractor=None,
            entries=[],
            base_name="Example Game (Disc 1)",
        )

        lines = _menu_option_lines(session, None)

        self.assertIn(
            "4. Dump active file to hex file (<filename>.hex)",
            lines,
        )
        self.assertIn(
            "5. Dump filesystem to one hex blob (Example Game (Disc 1).hex)",
            lines,
        )
        self.assertIn(
            "6. Structured image dump "
            "(extracted_output/Example Game (Disc 1)/)",
            lines,
        )
        self.assertIn(
            "7. Portable structured dump "
            "(extracted_output/Example Game (Disc 1)-dump.zip)",
            lines,
        )

    def test_selected_file_previews_real_file_hex_name(self):
        session = DiscSession(
            source_path=r"C:\images\Game.cue",
            source=object(),
            reader=None,
            extractor=None,
            entries=[],
            base_name="Game",
        )
        entry = ISO9660Entry(
            name="SAMPLE.DAT",
            raw_name="SAMPLE.DAT;1",
            lba=0,
            size=143360,
            is_dir=False,
        )

        lines = _menu_option_lines(session, ("/SAMPLE.DAT", entry))

        self.assertIn(
            "4. Dump active file to hex file (SAMPLE.DAT.hex)",
            lines,
        )
        self.assertIn(
            "5. Dump filesystem to one hex blob (Game.hex)",
            lines,
        )
        self.assertIn(
            "6. Structured image dump (extracted_output/Game/)",
            lines,
        )
        self.assertIn(
            "7. Portable structured dump (extracted_output/Game-dump.zip)",
            lines,
        )


if __name__ == "__main__":
    unittest.main()
