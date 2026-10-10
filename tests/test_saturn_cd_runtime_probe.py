"""Regression tests for the read-only Saturn CD/filesystem evidence probe."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.cd_runtime_probe import (
    SaturnCdRuntimeProbeError,
    inspect_saturn_cd_runtime_evidence,
)
from rikai_kotoba.tools.saturn_cd_runtime_probe import main as probe_main


class SaturnCdRuntimeProbeTests(unittest.TestCase):
    def _build_gfs_fixture(self, root: Path):
        include = root / "SBL_601" / "SEGALIB" / "INCLUDE"
        library = root / "SBL_601" / "SEGALIB" / "LIB_ELF"
        sample = root / "EXAMPLES" / "GFS_SAMPLE"
        include.mkdir(parents=True)
        library.mkdir(parents=True)
        sample.mkdir(parents=True)

        header = include / "SEGA_GFS.H"
        header.write_text(
            "int GFS_Init(int, void *, void *);\n"
            "int GFS_NameToId(char *);\n"
            "int GFS_Load(int, int, void *, int);\n"
            "int GFS_GetFileSize(void *, int *, int *);\n",
            encoding="utf-8",
        )
        cdc_header = include / "SEGA_CDC.H"
        cdc_header.write_text("int CDC_CdInit(int);\n", encoding="utf-8")
        libgfs = library / "sega_gfs.a"
        libgfs.write_bytes(b"gfs-archive")
        libcdc = library / "SEGA_CDC.A"
        libcdc.write_bytes(b"cdc-archive")
        dgfs = library / "SEGADGFS.A"
        dgfs.write_bytes(b"dgfs-archive")
        source = sample / "sample.c"
        source.write_text(
            '#include "SEGA_GFS.H"\n'
            "void demo(void) { GFS_Init(0, 0, 0); GFS_Load(0, 0, 0, 0); }\n",
            encoding="utf-8",
        )
        makefile = sample / "makefile"
        makefile.write_text(
            "LIBS = ../../SBL_601/SEGALIB/LIB_ELF/sega_gfs.a "
            "../../SBL_601/SEGALIB/LIB_ELF/SEGA_CDC.A\n",
            encoding="utf-8",
        )
        return header, libgfs, libcdc, source, makefile

    def test_finds_gfs_libraries_headers_contract_and_link_evidence_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Saturn-Dev"
            header, libgfs, libcdc, _source, makefile = self._build_gfs_fixture(root)

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
            contract_symbols = {
                symbol.casefold()
                for match in report.api_contract_matches
                for symbol in match.symbols
            }
            self.assertIn("gfs_nametoid", contract_symbols)
            self.assertIn("gfs_getfilesize", contract_symbols)
            self.assertTrue(
                any(match.path == makefile.resolve() for match in report.link_matches)
            )
            roles = {artifact.role for artifact in report.preferred_artifacts}
            self.assertEqual(
                roles,
                {
                    "gfs-header",
                    "cdc-header",
                    "gfs-library",
                    "cdc-library",
                    "dgfs-library",
                },
            )
            self.assertGreaterEqual(report.scanned_text_files, 4)

    def test_contract_only_cli_prioritizes_private_dependency_fingerprints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Saturn-Dev"
            self._build_gfs_fixture(root)
            output = StringIO()

            with redirect_stdout(output):
                result = probe_main(
                    [
                        "--saturn-root",
                        str(root),
                        "--contract-only",
                    ]
                )

            rendered = output.getvalue()
            self.assertEqual(result, 0)
            self.assertIn("Preferred installed SBL artifacts", rendered)
            self.assertIn("Prioritized GFS API contract lines", rendered)
            self.assertIn("Local GFS/CDC build-link evidence", rendered)
            self.assertIn("gfs-library", rendered)
            self.assertIn("SHA-256", rendered)
            self.assertNotIn("GFS textual evidence\n", rendered)

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
