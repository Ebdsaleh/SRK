"""Regression checks for the documented Sega GFS contracts used by Stage 6B."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_packaged_pcm.c"


class SaturnStage6BGfsSemanticsTests(unittest.TestCase):
    def test_loader_uses_documented_init_open_size_and_load_semantics(self):
        runtime = RUNTIME.read_text(encoding="utf-8")

        self.assertIn("result = GFS_Init", runtime)
        self.assertIn("if(result < 0)", runtime)

        self.assertIn("handle = GFS_Open(fid);", runtime)
        self.assertIn("if(handle == (GfsHn)0)", runtime)

        self.assertIn(
            "((unsigned long)(sector_count - 1) * (unsigned long)sector_size)",
            runtime,
        )
        self.assertIn("(unsigned long)last_size", runtime)
        self.assertIn(
            "file_size != SRK_SATURN_PACKAGED_PCM_FILE_BYTES",
            runtime,
        )

        self.assertIn("result = GFS_Load", runtime)
        self.assertIn(
            "result != (Sint32)SRK_SATURN_PACKAGED_PCM_FILE_BYTES",
            runtime,
        )

    def test_gfs_load_destination_remains_four_byte_aligned_and_bounded(self):
        runtime = RUNTIME.read_text(encoding="utf-8")

        self.assertIn("static Uint32 srk_pcm_file_words", runtime)
        self.assertIn(
            "(SRK_SATURN_PACKAGED_PCM_FILE_BYTES + 3u) / 4u",
            runtime,
        )
        self.assertIn("srk_pcm_file_words,", runtime)
        self.assertIn("(Sint32)SRK_SATURN_PACKAGED_PCM_FILE_BYTES", runtime)


if __name__ == "__main__":
    unittest.main()
