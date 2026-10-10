"""Legacy SH-ELF text-input compatibility contracts."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.standalone_project import (
    _copy_text_with_final_newline,
)


class SaturnStandaloneTextCompatTests(unittest.TestCase):
    def test_copy_text_adds_exactly_one_final_lf_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.h"
            destination = root / "destination.h"
            source.write_bytes(b"#endif")

            _copy_text_with_final_newline(source, destination)

            self.assertEqual(destination.read_bytes(), b"#endif\n")
            self.assertEqual(source.read_bytes(), b"#endif")

    def test_copy_text_preserves_existing_final_lf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.c"
            destination = root / "destination.c"
            source.write_bytes(b"int x;\n")

            _copy_text_with_final_newline(source, destination)

            self.assertEqual(destination.read_bytes(), b"int x;\n")


if __name__ == "__main__":
    unittest.main()
