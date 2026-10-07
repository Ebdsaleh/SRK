from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.toolchain import (
    SAROO_TOOL_REQUIREMENTS,
    SarooToolchainError,
    inspect_saroo_toolchain,
)


class SarooToolchainTests(unittest.TestCase):
    def _populate_toolchain(self, root: Path) -> Path:
        bin_dir = root / "SaturnOrbit" / "toolchains" / "sh-elf" / "bin"
        bin_dir.mkdir(parents=True)
        for requirement in SAROO_TOOL_REQUIREMENTS:
            filename = (
                "mingw32-make.exe"
                if requirement.name == "make"
                else requirement.name + ".exe"
            )
            (bin_dir / filename).write_bytes(b"synthetic-tool")
        return bin_dir

    def test_explicit_saturnorbit_root_resolves_every_required_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = self._populate_toolchain(root)

            report = inspect_saroo_toolchain(root, path_env="")

            self.assertTrue(report.ready)
            self.assertEqual(report.missing, ())
            self.assertEqual(report.search_root, root.resolve())
            for probe in report.probes:
                self.assertTrue(probe.available)
                self.assertEqual(probe.source, "toolchain-root")
                self.assertEqual(probe.resolved_path.parent, bin_dir.resolve())

    def test_missing_tools_are_reported_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sh-elf-gcc.exe").write_bytes(b"compiler")

            report = inspect_saroo_toolchain(root, path_env="")

            self.assertFalse(report.ready)
            self.assertIsNotNone(report.path_for("sh-elf-gcc"))
            self.assertIn("sh-elf-as", report.missing)
            self.assertIn("sh-elf-objdump", report.missing)
            self.assertIn("sh-elf-objcopy", report.missing)
            self.assertIn("make", report.missing)

    def test_make_compatible_alias_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._populate_toolchain(root)

            report = inspect_saroo_toolchain(root, path_env="")

            make_path = report.path_for("make")
            self.assertIsNotNone(make_path)
            self.assertEqual(make_path.name.casefold(), "mingw32-make.exe")

    def test_invalid_explicit_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "does-not-exist"
            with self.assertRaises(SarooToolchainError):
                inspect_saroo_toolchain(missing, path_env="")

    def test_preflight_does_not_modify_process_path(self) -> None:
        before = os.environ.get("PATH")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._populate_toolchain(root)
            inspect_saroo_toolchain(root, path_env="")
        self.assertEqual(os.environ.get("PATH"), before)


if __name__ == "__main__":
    unittest.main()
