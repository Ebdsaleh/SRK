"""Source-contract checks for the optional SAROO Firm_Saturn helper."""

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.saroo import SAROO_SD_WRITE_CHUNK_SIZE


class SarooFirmwareHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.integration_root = (
            Path(__file__).resolve().parents[1]
            / "integrations"
            / "saroo"
            / "Firm_Saturn"
        )
        cls.header = (cls.integration_root / "srk_capture_helper.h").read_text(
            encoding="utf-8"
        )
        cls.source = (cls.integration_root / "srk_capture_helper.c").read_text(
            encoding="utf-8"
        )

    def test_c_helper_uses_same_verified_chunk_size_as_python_contract(self):
        expected = f"#define SRK_CAPTURE_CHUNK_SIZE 0x{SAROO_SD_WRITE_CHUNK_SIZE:08X}u"
        self.assertIn(expected, self.header)

    def test_c_helper_uses_upstream_create_then_explicit_offset_writes(self):
        self.assertIn("file_offset = (offset==0) ? -1 : (int)offset;", self.source)
        self.assertIn("written = write_file(", self.source)
        self.assertIn("if((unsigned int)written!=chunk)", self.source)

    def test_c_helper_wrappers_are_title_neutral_canonical_work_ram_ranges(self):
        self.assertIn("#define SRK_WORK_RAM_LOW_START   0x00200000u", self.source)
        self.assertIn("#define SRK_WORK_RAM_HIGH_START  0x06000000u", self.source)
        self.assertIn("#define SRK_WORK_RAM_SIZE        0x00100000u", self.source)


if __name__ == "__main__":
    unittest.main()
