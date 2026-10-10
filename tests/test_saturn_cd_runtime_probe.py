"""Regression tests for the read-only Saturn CD/filesystem evidence probe."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.cd_runtime_probe import (
    SaturnCdRuntimeProbeError,
    inspect_saturn_cd_runtime_evidence,
)


class SaturnCdRuntimeProbeTests(unittest.TestCase):
    def test_finds_gfs_libraries_headers_and_symbol_evidence_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Saturn-Dev"
            include = root / "SBL_601" / "SEGALIB" / "INCLUDE"
            library = root / "SBL_601" / "SEGALIB" / "LIB_ELF"
            sample = root / "EXAMPLES" / "GFS_SAMPLE"
            include.mkdir(parents=True)
            library.mkdir(parents=True)
            sample.mkdir(parents=True)

            header = include / "SEGA_GFS.H"
            header.write_text(
                "int GFS_Init(int, void *, void *);\n"
                "int GFS_Load(int, int, void *, int);\n",
                encoding="utf-8",
            )
            libgfs = library / "LIBGFS.A"
            libgfs.write_bytes(b"archive")
            libcdc = library / "LIBCDC.A"
            libcdc.write_bytes(b"archive")
            source = sample / "sample.c"
            source.write_text(
                '#include "SEGA_GFS.H"\n'
                "void demo(void) { GFS_Init(0, 0, 0); GFS_Load(0, 0, 0, 0); }\n",
                encoding="utf-8",
            )

            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            report = inspect_saturn_cd_runtime_evidence(root)
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }

            self.assertEqual(before, after)
            self.assertIn(libgfs.resolve(), report.libraries)
            self.assertIn(libcdc.resolve(), report.libraries)
            self.assertIn(header.resolve(), report.likely_headers)
            symbols = {
                symbol.casefold()
                for match in report.text_matches
                for symbol in match.symbols
            }
            self.assertIn("gfs_init", symbols)
            self.assertIn("gfs_load", symbols)
            self.assertGreaterEqual(report.scanned_text_files, 2)

    def test_ignores_unrelated_text_outside_relevant_saturn_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Saturn-Dev"
            unrelated = root / "toolchain" / "notes.c"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("GFS_Fake();\n", encoding="utf-8")

            report = inspect_saturn_cd_runtime_evidence(root)

            self.assertEqual(report.text_matches, tuple())
            self.assertEqual(report.scanned_text_files, 0)

    def test_rejects_missing_saturn_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaises(SaturnCdRuntimeProbeError):
                inspect_saturn_cd_runtime_evidence(missing)


if __name__ == "__main__":
    unittest.main()
