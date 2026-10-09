"""Tests for Python-native standalone Saturn build orchestration."""

from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from rikai_kotoba.formats.saturn.mode1_image import verify_mode1_bin_against_iso
from rikai_kotoba.hardware.saturn.standalone_build import (
    SaturnStandaloneBuildError,
    build_saturn_standalone_project,
)
from rikai_kotoba.hardware.saturn.standalone_project import (
    prepare_saturn_standalone_project,
)


def _field(text: str, size: int) -> bytes:
    return text.encode("ascii").ljust(size, b" ")


def _ip_bin() -> bytes:
    data = bytearray(2048)
    data[0x00:0x10] = _field("SEGA SEGASATURN", 16)
    data[0x10:0x20] = _field("LOCAL TEMPLATE", 16)
    data[0x20:0x2A] = _field("OLD-TITLE", 10)
    data[0x2A:0x30] = _field("V9.999", 6)
    data[0x30:0x38] = _field("20000101", 8)
    data[0x38:0x40] = _field("CD-1/1", 8)
    data[0x40:0x4A] = _field("JTUE", 10)
    data[0x50:0x60] = _field("J", 16)
    data[0x60:0xD0] = _field("OLD TEMPLATE TITLE", 112)
    data[0xE0:0xE4] = (0x1800).to_bytes(4, "big")
    data[0xF0:0xF4] = (0x06004000).to_bytes(4, "big")
    data[0x100:0x110] = b"LOCAL-BOOT-CODE!"
    return bytes(data)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _prepared_project(root: Path) -> Path:
    saturn = root / "Saturn-Dev"
    bin_dir = saturn / "SH_ELF" / "sh-elf" / "bin"
    for name in (
        "sh-elf-gcc.exe",
        "sh-elf-as.exe",
        "sh-elf-objdump.exe",
        "sh-elf-objcopy.exe",
    ):
        _touch(bin_dir / name)
    _touch(saturn / "TOOLS" / "mkisofs.exe")

    template = root / "vdp1ex"
    template.mkdir()
    (template / "vga_font.h").write_text(
        "unsigned char font[2048] = {0};\n",
        encoding="utf-8",
    )
    ip_bin = root / "IP.BIN"
    ip_bin.write_bytes(_ip_bin())

    output = root / "SRK-Diagnostics-R1"
    prepare_saturn_standalone_project(
        saturn,
        template,
        ip_bin,
        output,
        release_date="20261009",
    )
    return output


class _SuccessfulRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((tuple(argv), dict(kwargs)))
        root = Path(kwargs["cwd"])
        self._assert_direct(kwargs)

        if "-o" in argv:
            output = root / argv[argv.index("-o") + 1]
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.suffix.casefold() == ".iso":
                output.write_bytes(bytes((index * 13) & 0xFF for index in range(4096)))
            else:
                output.write_bytes(("artifact:" + output.name).encode("ascii"))

        for item in argv:
            if item.startswith("-Wl,-Map,"):
                map_path = root / item[len("-Wl,-Map,"):]
                map_path.parent.mkdir(parents=True, exist_ok=True)
                map_path.write_text("map\n", encoding="ascii")

        return subprocess.CompletedProcess(argv, 0, stdout=b"ok\n")

    @staticmethod
    def _assert_direct(kwargs):
        if kwargs.get("shell") is not False:
            raise AssertionError("builder must use shell=False")


class _FailFirstRunner:
    def __init__(self):
        self.calls = 0

    def __call__(self, argv, **kwargs):
        self.calls += 1
        if kwargs.get("shell") is not False:
            raise AssertionError("builder must use shell=False")
        return subprocess.CompletedProcess(argv, 1, stdout=b"synthetic compiler failure\n")


class SaturnStandaloneBuildTests(unittest.TestCase):
    def test_python_builder_invokes_tools_directly_and_publishes_hashes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            watched = {
                path: path.read_bytes()
                for path in (project / "src").iterdir()
                if path.is_file()
            }
            runner = _SuccessfulRunner()

            result = build_saturn_standalone_project(project, _runner=runner)

            self.assertTrue(result.successful)
            self.assertEqual(len(runner.calls), 10)
            self.assertTrue((project / "build" / "srk_diag.bin").is_file())
            iso = project / "build" / "srk_diag.iso"
            self.assertTrue(iso.is_file())
            self.assertTrue((project / "cd" / "0.bin").is_file())
            deploy = project / "build" / "SRK-Diagnostics"
            raw = deploy / "SRK-Diagnostics.bin"
            cue = deploy / "SRK-Diagnostics.cue"
            self.assertTrue(raw.is_file())
            self.assertTrue(cue.is_file())
            self.assertEqual(verify_mode1_bin_against_iso(iso, raw), 2)
            self.assertEqual(raw.stat().st_size, 2 * 2352)
            self.assertEqual(
                cue.read_bytes(),
                b'FILE "SRK-Diagnostics.bin" BINARY\r\n'
                b"  TRACK 01 MODE1/2352\r\n"
                b"    INDEX 01 00:00:00\r\n",
            )
            self.assertTrue(result.log_path.is_file())
            self.assertTrue(result.report_path.is_file())
            self.assertEqual(
                {path: path.read_bytes() for path in watched},
                watched,
            )
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["orchestration"], "python-native")
            self.assertTrue(report["successful"])
            self.assertFalse(report["policy"]["shell_used"])
            self.assertFalse(report["policy"]["path_mutated"])
            self.assertEqual(len(report["artifacts"]), 6)
            self.assertEqual(report["deployable"]["format"], "cue-bin-mode1-2352")
            self.assertEqual(
                report["deployable"]["cue"],
                "build/SRK-Diagnostics/SRK-Diagnostics.cue",
            )
            self.assertEqual(
                report["deployable"]["bin"],
                "build/SRK-Diagnostics/SRK-Diagnostics.bin",
            )
            self.assertTrue(report["deployable"]["verified_against_iso"])

    def test_failure_stops_at_first_command_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            runner = _FailFirstRunner()

            result = build_saturn_standalone_project(project, _runner=runner)

            self.assertFalse(result.successful)
            self.assertEqual(runner.calls, 1)
            self.assertTrue(result.log_path.is_file())
            self.assertTrue(result.report_path.is_file())
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["successful"])
            self.assertIn(
                "synthetic compiler failure",
                result.log_path.read_text(encoding="utf-8"),
            )

    def test_tampered_generated_input_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            target = project / "src" / "srk_diag_app.c"
            target.write_text(target.read_text(encoding="utf-8") + "\n/* tamper */\n", encoding="utf-8")
            runner = _SuccessfulRunner()

            with self.assertRaises(SaturnStandaloneBuildError):
                build_saturn_standalone_project(project, _runner=runner)

            self.assertEqual(runner.calls, [])

    def test_existing_build_output_is_rejected_to_preserve_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            (project / "build" / "old.bin").write_bytes(b"old")

            with self.assertRaises(SaturnStandaloneBuildError):
                build_saturn_standalone_project(project, _runner=_SuccessfulRunner())

    def test_second_python_build_attempt_requires_fresh_generated_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            first = build_saturn_standalone_project(project, _runner=_SuccessfulRunner())
            self.assertTrue(first.successful)

            with self.assertRaises(SaturnStandaloneBuildError):
                build_saturn_standalone_project(project, _runner=_SuccessfulRunner())


if __name__ == "__main__":
    unittest.main()
