"""Tests for read-only standalone Saturn environment discovery."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.standalone_environment import (
    SaturnStandaloneEnvironmentError,
    inspect_saturn_standalone_environment,
)
from rikai_kotoba.tools.saturn_standalone_probe import main as probe_main


def _touch(path: Path, data: bytes = b"test\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _complete_root(base: Path, *, sample_count: int = 1) -> Path:
    root = base / "SaturnOrbit"
    tool_bin = root / "SH_ELF" / "sh-elf" / "bin"
    for name in (
        "sh-elf-gcc.exe",
        "sh-elf-as.exe",
        "sh-elf-objdump.exe",
        "sh-elf-objcopy.exe",
    ):
        _touch(tool_bin / name)

    _touch(root / "SGL_302j" / "INC" / "SL_DEF.H")
    _touch(root / "SGL_302j" / "LIB" / "SEGA_SYS.A")
    for index in range(sample_count):
        _touch(root / "SGL_302j" / "SAMPLE" / f"S_{index:02d}" / "Makefile")
    _touch(root / "SGL_302j" / "SAMPLE" / "S_00" / "IP.BIN", b"IP")

    _touch(root / "MinGW" / "bin" / "make.exe")
    _touch(root / "MinGW" / "bin" / "mkisofs.exe")
    _touch(root / "tools" / "IPMaker.exe")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class SaturnStandaloneEnvironmentTests(unittest.TestCase):
    def test_detects_compiler_sgl_samples_ip_and_helper_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _complete_root(Path(temp_dir))
            report = inspect_saturn_standalone_environment(root, path_env="")

            self.assertTrue(report.compiler_ready)
            self.assertTrue(report.sgl_detected)
            self.assertTrue(report.samples_detected)
            self.assertTrue(report.ip_asset_detected)
            self.assertEqual(len(report.sgl_headers), 1)
            self.assertEqual(len(report.libraries), 1)
            self.assertEqual(len(report.sample_makefiles), 1)
            self.assertEqual(len(report.ip_bin_assets), 1)
            self.assertTrue(report.tool_for("make").available)
            self.assertTrue(report.tool_for("iso-builder").available)
            self.assertTrue(report.tool_for("ip-builder").available)

    def test_sample_report_is_bounded_without_changing_discovery_semantics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _complete_root(Path(temp_dir), sample_count=7)
            report = inspect_saturn_standalone_environment(
                root,
                path_env="",
                sample_limit=3,
            )

            self.assertTrue(report.samples_detected)
            self.assertEqual(len(report.sample_makefiles), 3)
            self.assertTrue(
                all(path.name.casefold() == "makefile" for path in report.sample_makefiles)
            )

    def test_probe_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _complete_root(Path(temp_dir), sample_count=2)
            before = _snapshot(root)

            inspect_saturn_standalone_environment(root, path_env="")

            self.assertEqual(_snapshot(root), before)

    def test_empty_root_reports_missing_optional_evidence_without_guessing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "SaturnOrbit"
            root.mkdir()

            report = inspect_saturn_standalone_environment(root, path_env="")

            self.assertFalse(report.compiler_ready)
            self.assertFalse(report.sgl_detected)
            self.assertFalse(report.samples_detected)
            self.assertFalse(report.ip_asset_detected)
            self.assertTrue(all(not probe.available for probe in report.tools))

    def test_invalid_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaises(SaturnStandaloneEnvironmentError):
                inspect_saturn_standalone_environment(missing, path_env="")

    def test_cli_reports_read_only_environment_and_local_sample(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _complete_root(Path(temp_dir))
            output = StringIO()

            with redirect_stdout(output):
                status = probe_main(["--saturn-root", str(root)])

            text = output.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("READ-ONLY", text)
            self.assertIn("Compiler set     : READY", text)
            self.assertIn("SGL tree         : FOUND", text)
            self.assertIn("Sample templates : FOUND", text)
            self.assertIn("S_00", text)
            self.assertIn("No files were modified.", text)


if __name__ == "__main__":
    unittest.main()
