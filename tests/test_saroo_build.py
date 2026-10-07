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
            (bin_dir / (requirement.name + ".exe")).write_bytes(b"synthetic-tool")
        return bin_dir

    @staticmethod
    def _generated_tree(root: Path) -> Path:
        generated = root / "SAROO-SRK"
        firm = generated / "Firm_Saturn"
        firm.mkdir(parents=True)
        (generated / "SRK_INTEGRATION.txt").write_text(
            "synthetic\n",
            encoding="utf-8",
        )
        (firm / "Makefile").write_text(
            "CC = sh-elf-gcc\n"
            "AS = sh-elf-as\n"
            "OBJDUMP = sh-elf-objdump\n"
            "OBJCOPY = sh-elf-objcopy\n"
            "LDFLAGS = -nostartfiles -T ldscript\n"
            "FLAGS = -Wall -m2 -Os -fomit-frame-pointer -std=c99\n"
            "LIBS = -lgcc\n"
            "EXE = ssfirm.elf\n"
            "OBJ = obj/crt0.o \\\n"
            "      obj/main.o \\\n"
            "      obj/srk_capture_helper.o\n",
            encoding="utf-8",
        )
        (firm / "srk_build_support.py").write_text(
            "# synthetic\n",
            encoding="utf-8",
        )
        (firm / "crt0.S").write_text("synthetic\n", encoding="utf-8")
        (firm / "main.c").write_text("synthetic\n", encoding="utf-8")
        (firm / "srk_capture_helper.c").write_text(
            "synthetic\n",
            encoding="utf-8",
        )
        (firm / "version.c").write_text("synthetic\n", encoding="utf-8")
        (firm / "font_cjk.bin").write_bytes(b"FONT")
        (firm / "ldscript").write_text("synthetic\n", encoding="utf-8")
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
            (firm / "srk_build_support.py").write_text(
                "# synthetic\n",
                encoding="utf-8",
            )
            toolchain = root / "toolchain-root"
            self._populate_toolchain(toolchain)

            with self.assertRaisesRegex(SarooBuildError, "integration marker"):
                build_firm_saturn_tree(generated, toolchain, progress=None)

    @patch("rikai_kotoba.hardware.saturn.saroo.build._run_command")
    def test_native_build_invokes_sh_elf_tools_directly_and_hashes_artifacts(
        self,
        run_command,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolchain = root / "toolchain-root"
            tool_bin = self._populate_toolchain(toolchain)
            generated = self._generated_tree(root)
            firm = generated / "Firm_Saturn"
            before_path = os.environ.get("PATH")
            before_shell = os.environ.get("SHELL")
            progress: list[str] = []

            def fake_run(command, *, cwd, env, on_output=None):
                tool = Path(command[0]).name.casefold()
                if tool == "sh-elf-gcc.exe" and "-c" in command:
                    output_name = command[command.index("-o") + 1]
                    output_path = cwd / Path(
                        *output_name.replace("\\", "/").split("/")
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(("OBJ:" + output_name).encode("ascii"))
                    if on_output is not None:
                        on_output("synthetic compiler output")
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        "synthetic compiler output\n",
                    )

                if tool == "sh-elf-as.exe":
                    output_name = command[command.index("-o") + 1]
                    output_path = cwd / Path(
                        *output_name.replace("\\", "/").split("/")
                    )
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(("OBJ:" + output_name).encode("ascii"))
                    return subprocess.CompletedProcess(command, 0, "")

                if tool == "sh-elf-gcc.exe":
                    output_name = command[command.index("-o") + 1]
                    (cwd / output_name).write_bytes(b"ELF")
                    return subprocess.CompletedProcess(command, 0, "")

                if tool == "sh-elf-objdump.exe":
                    return subprocess.CompletedProcess(command, 0, "DUMP\n")

                if tool == "sh-elf-objcopy.exe":
                    output_name = command[-1]
                    (cwd / output_name).write_bytes(b"BIN")
                    return subprocess.CompletedProcess(command, 0, "")

                raise AssertionError(f"unexpected command: {command}")

            run_command.side_effect = fake_run

            result = build_firm_saturn_tree(
                generated,
                toolchain,
                progress=progress.append,
            )

            self.assertTrue(result.successful)
            self.assertEqual(result.clean_returncode, 0)
            self.assertEqual(result.build_returncode, 0)
            self.assertEqual(run_command.call_count, 6)
            self.assertEqual(os.environ.get("PATH"), before_path)
            self.assertEqual(os.environ.get("SHELL"), before_shell)

            for call in run_command.call_args_list:
                child_path = call.kwargs["env"]["PATH"]
                child_entries = [
                    Path(value) for value in child_path.split(os.pathsep) if value
                ]
                self.assertTrue(
                    any(
                        entry.exists() and os.path.samefile(tool_bin, entry)
                        for entry in child_entries
                    )
                )
                self.assertEqual(call.kwargs["env"].get("SHELL"), before_shell)

            command_tools = [
                Path(call.args[0][0]).name.casefold()
                for call in run_command.call_args_list
            ]
            self.assertEqual(
                command_tools,
                [
                    "sh-elf-as.exe",
                    "sh-elf-gcc.exe",
                    "sh-elf-gcc.exe",
                    "sh-elf-gcc.exe",
                    "sh-elf-objdump.exe",
                    "sh-elf-objcopy.exe",
                ],
            )

            expected_payloads = {
                "ssfirm.elf": b"ELF",
                "ssfirm.bin": b"BINFONT",
                "dump.txt": b"DUMP\n",
            }
            artifacts = {artifact.path.name: artifact for artifact in result.artifacts}
            self.assertEqual(set(artifacts), set(expected_payloads))
            for name, data in expected_payloads.items():
                self.assertEqual((firm / name).read_bytes(), data)
                self.assertEqual(artifacts[name].size, len(data))
                self.assertEqual(artifacts[name].sha256, sha256(data).hexdigest())

            self.assertFalse((firm / "tmp.bin").exists())
            self.assertTrue(result.log_path.is_file())
            log_text = result.log_path.read_text(encoding="utf-8")
            self.assertIn(
                "Build driver: SRK Python native (GNU Make not required)",
                log_text,
            )
            self.assertIn("Shell mediation: none", log_text)
            self.assertNotIn("make.exe", log_text.casefold())
            self.assertIn("synthetic compiler output", log_text)
            self.assertIn("Build result: SUCCESS", log_text)
            self.assertTrue(any("Compiling 3" in line for line in progress))
            self.assertTrue(any("Build result: SUCCESS" in line for line in progress))

    @patch("rikai_kotoba.hardware.saturn.saroo.build._run_command")
    def test_failed_compile_is_logged_and_later_build_steps_are_not_started(
        self,
        run_command,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolchain = root / "toolchain-root"
            self._populate_toolchain(toolchain)
            generated = self._generated_tree(root)

            run_command.return_value = subprocess.CompletedProcess(
                ["sh-elf-as", "crt0.S"],
                2,
                "compile failed\n",
            )

            result = build_firm_saturn_tree(
                generated,
                toolchain,
                progress=None,
            )

            self.assertFalse(result.successful)
            self.assertEqual(result.clean_returncode, 0)
            self.assertEqual(result.build_returncode, 2)
            self.assertEqual(run_command.call_count, 1)
            log_text = result.log_path.read_text(encoding="utf-8")
            self.assertIn("Compilation stopped at: crt0.S", log_text)
            self.assertIn("Build result: FAILED", log_text)

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
