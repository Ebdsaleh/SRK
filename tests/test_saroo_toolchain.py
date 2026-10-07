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
            (bin_dir / (requirement.name + ".exe")).write_bytes(b"synthetic-tool")
        return bin_dir

    def test_native_build_requires_only_external_sh_elf_tools(self) -> None:
        self.assertEqual(
            tuple(requirement.name for requirement in SAROO_TOOL_REQUIREMENTS),
            (
                "sh-elf-gcc",
                "sh-elf-as",
                "sh-elf-objdump",
                "sh-elf-objcopy",
            ),
        )
        self.assertNotIn(
            "make",
            tuple(requirement.name for requirement in SAROO_TOOL_REQUIREMENTS),
        )

    def test_explicit_saturnorbit_root_resolves_every_required_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bin_dir = self._populate_toolchain(root)

            report = inspect_saroo_toolchain(root, path_env="")

            self.assertTrue(report.ready)
            self.assertEqual(report.missing, ())
            self.assertIsNotNone(report.search_root)
            self.assertTrue(os.path.samefile(report.search_root, root))
            for probe in report.probes:
                self.assertTrue(probe.available)
                self.assertEqual(probe.source, "toolchain-root")
                self.assertIsNotNone(probe.resolved_path)
                self.assertTrue(os.path.samefile(probe.resolved_path.parent, bin_dir))

    def test_missing_tools_are_reported_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sh-elf-gcc.exe").write_bytes(b"compiler")

            report = inspect_saroo_toolchain(root, path_env="")

            self.assertFalse(report.ready)
            self.assertIsNotNone(report.path_for("sh-elf-gcc"))
            for required_name in (
                "sh-elf-as",
                "sh-elf-objdump",
                "sh-elf-objcopy",
            ):
                with self.subTest(required_name=required_name):
                    self.assertIn(required_name, report.missing)

            for no_longer_required in ("make", "touch", "cat", "rm"):
                with self.subTest(no_longer_required=no_longer_required):
                    self.assertNotIn(no_longer_required, report.missing)
                    self.assertIsNone(report.path_for(no_longer_required))

    def test_physical_saturnorbit_r1_layout_resolves_native_build_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler_bin = root / "SH_ELF" / "sh-elf" / "bin"
            compiler_bin.mkdir(parents=True)

            for name in (
                "sh-elf-gcc.exe",
                "sh-elf-as.exe",
                "sh-elf-objdump.exe",
                "sh-elf-objcopy.exe",
            ):
                (compiler_bin / name).write_bytes(b"synthetic-tool")

            # SaturnOrbit R1 may also contain an ancient GNU Make. The native
            # SRK build path deliberately does not require or resolve it.
            utility_bin = root / "SH_ELF" / "Other Utilities"
            utility_bin.mkdir(parents=True)
            (utility_bin / "make.exe").write_bytes(b"legacy-make")

            report = inspect_saroo_toolchain(root, path_env="")

            self.assertTrue(report.ready)
            self.assertTrue(
                os.path.samefile(report.path_for("sh-elf-gcc").parent, compiler_bin)
            )
            self.assertIsNone(report.path_for("make"))

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
