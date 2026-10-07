from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rikai_kotoba.cli import main as srk_cli_main
from rikai_kotoba.hardware.saturn.saroo import (
    SAROO_TOOL_REQUIREMENTS,
    SarooBuildArtifact,
    SarooBuildError,
    SarooBuildResult,
    build_firm_saturn_tree,
)
from rikai_kotoba.tools.saroo_build import main as build_cli_main


class SarooBuildTests(unittest.TestCase):
    @staticmethod
    def _populate_toolchain(root: Path) -> Path:
        bin_dir = root / "toolchain" / "bin"
        bin_dir.mkdir(parents=True)
        for requirement in SAROO_TOOL_REQUIREMENTS:
            name = "make.exe" if requirement.name == "make" else requirement.name + ".exe"
            (bin_dir / name).write_bytes(b"synthetic-tool")
        return bin_dir

    @staticmethod
    def _generated_tree(root: Path) -> Path:
        generated = root / "SAROO-SRK"
        firm = generated / "Firm_Saturn"
        firm.mkdir(parents=True)
        (generated / "SRK_INTEGRATION.txt").write_text("synthetic\n", encoding="utf-8")
        (firm / "Makefile").write_text("all:\n\t@echo synthetic\n", encoding="utf-8")
        (firm / "srk_build_support.py").write_text("# synthetic\n", encoding="utf-8")
        return generated

    @staticmethod
    def _successful_result() -> SarooBuildResult:
        artifact = SarooBuildArtifact(
            path=Path("ssfirm.bin"),
            size=3,
            sha256="abc123",
        )
        return SarooBuildResult(
            generated_root=Path("SAROO-SRK"),
            firm_saturn_directory=Path("SAROO-SRK/Firm_Saturn"),
            toolchain_root=Path("SaturnOrbit"),
            log_path=Path("SAROO-SRK/SRK_BUILD_LOG.txt"),
            clean_returncode=0,
            build_returncode=0,
            artifacts=(artifact,),
            successful=True,
        )

    def test_refuses_arbitrary_saroo_tree_without_integration_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generated = root / "upstream"
            firm = generated / "Firm_Saturn"
            firm.mkdir(parents=True)
            (firm / "Makefile").write_text("all:\n", encoding="utf-8")
            (firm / "srk_build_support.py").write_text("# synthetic\n", encoding="utf-8")
            toolchain = root / "toolchain-root"
            self._populate_toolchain(toolchain)

            with self.assertRaisesRegex(SarooBuildError, "integration marker"):
                build_firm_saturn_tree(generated, toolchain)

    @patch("rikai_kotoba.hardware.saturn.saroo.build._run_make")
    def test_controlled_build_uses_process_local_tools_and_hashes_artifacts(self, run_make) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolchain = root / "toolchain-root"
            tool_bin = self._populate_toolchain(toolchain)
            generated = self._generated_tree(root)
            firm = generated / "Firm_Saturn"
            before_path = os.environ.get("PATH")
            before_shell = os.environ.get("SHELL")

            payloads = {
                "ssfirm.elf": b"ELF",
                "ssfirm.bin": b"BIN",
                "dump.txt": b"DUMP",
            }

            def fake_run(command, *, cwd, env):
                if command[-1] == "clean":
                    return subprocess.CompletedProcess(command, 0, "clean ok\n")
                for name, data in payloads.items():
                    (cwd / name).write_bytes(data)
                return subprocess.CompletedProcess(command, 0, "build ok\n")

            run_make.side_effect = fake_run

            result = build_firm_saturn_tree(generated, toolchain)

            self.assertTrue(result.successful)
            self.assertEqual(result.clean_returncode, 0)
            self.assertEqual(result.build_returncode, 0)
            self.assertEqual(run_make.call_count, 2)
            self.assertEqual(os.environ.get("PATH"), before_path)
            self.assertEqual(os.environ.get("SHELL"), before_shell)

            clean_call = run_make.call_args_list[0]
            child_path = clean_call.kwargs["env"]["PATH"]
            child_entries = [Path(value) for value in child_path.split(os.pathsep) if value]
            self.assertTrue(
                any(
                    entry.exists() and os.path.samefile(tool_bin, entry)
                    for entry in child_entries
                )
            )
            self.assertEqual(clean_call.kwargs["env"]["SHELL"], "cmd.exe")
            self.assertTrue(clean_call.args[0][0].endswith("make.exe"))
            self.assertIn("SHELL=cmd.exe", clean_call.args[0])
            self.assertEqual(clean_call.args[0][-1], "clean")

            build_call = run_make.call_args_list[1]
            self.assertEqual(build_call.kwargs["env"]["SHELL"], "cmd.exe")
            self.assertIn("SHELL=cmd.exe", build_call.args[0])

            artifacts = {artifact.path.name: artifact for artifact in result.artifacts}
            self.assertEqual(set(artifacts), set(payloads))
            for name, data in payloads.items():
                self.assertEqual(artifacts[name].size, len(data))
                self.assertEqual(artifacts[name].sha256, sha256(data).hexdigest())

            self.assertTrue(result.log_path.is_file())
            log_text = result.log_path.read_text(encoding="utf-8")
            self.assertIn("Make recipe shell: cmd.exe (explicit override)", log_text)
            self.assertIn("SHELL=cmd.exe", log_text)
            self.assertIn("clean ok", log_text)
            self.assertIn("build ok", log_text)
            self.assertIn("Build result: SUCCESS", log_text)

    @patch("rikai_kotoba.hardware.saturn.saroo.build._run_make")
    def test_failed_clean_is_logged_and_build_is_not_started(self, run_make) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolchain = root / "toolchain-root"
            self._populate_toolchain(toolchain)
            generated = self._generated_tree(root)
            run_make.return_value = subprocess.CompletedProcess(
                ["make", "clean"], 2, "clean failed\n"
            )

            result = build_firm_saturn_tree(generated, toolchain)

            self.assertFalse(result.successful)
            self.assertEqual(result.clean_returncode, 2)
            self.assertIsNone(result.build_returncode)
            self.assertEqual(run_make.call_count, 1)
            self.assertIn("clean failed", result.log_path.read_text(encoding="utf-8"))

    def test_cli_reports_success_without_deployment_language(self) -> None:
        result = self._successful_result()
        output = StringIO()
        with patch(
            "rikai_kotoba.tools.saroo_build.build_firm_saturn_tree",
            return_value=result,
        ), redirect_stdout(output):
            code = build_cli_main(
                ["SAROO-SRK", "--toolchain-root", "SaturnOrbit"]
            )

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Build result: SUCCESS", text)
        self.assertIn("No firmware was copied to SD or flashed.", text)
        self.assertIn("abc123", text)

    def test_existing_srk_cli_exposes_controlled_saroo_build_without_reinstall(self) -> None:
        result = self._successful_result()
        output = StringIO()
        with patch(
            "rikai_kotoba.cli.build_firm_saturn_tree",
            return_value=result,
        ), redirect_stdout(output):
            code = srk_cli_main(
                [
                    "build-saroo-firmware",
                    "SAROO-SRK",
                    "--toolchain-root",
                    "SaturnOrbit",
                ]
            )

        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn("Build result: SUCCESS", text)
        self.assertIn("No firmware was copied to SD or flashed.", text)
        self.assertIn("abc123", text)


if __name__ == "__main__":
    unittest.main()
