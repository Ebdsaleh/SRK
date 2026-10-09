"""Tests for read-only inspection of one Saturn standalone template."""

from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.standalone_template import (
    SaturnStandaloneTemplateError,
    inspect_saturn_standalone_template,
)
from rikai_kotoba.tools.saturn_standalone_template_probe import main as probe_main


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _field(text: str, size: int) -> bytes:
    return text.encode("ascii").ljust(size, b" ")


def _ip_bin() -> bytes:
    data = bytearray(2048)
    data[0x00:0x10] = _field("SEGA SEGASATURN", 16)
    data[0x10:0x20] = _field("SEGA ENTERPRISES", 16)
    data[0x20:0x2A] = _field("T-0000G", 10)
    data[0x2A:0x30] = _field("V0.001", 6)
    data[0x30:0x38] = _field("20261009", 8)
    data[0x38:0x40] = _field("CD-1/1", 8)
    data[0x40:0x4A] = _field("JTUE", 10)
    data[0x4A:0x50] = b" " * 6
    data[0x50:0x60] = _field("J", 16)
    data[0x60:0xD0] = _field("SRK DIAGNOSTICS", 112)
    data[0xE0:0xE4] = (0x1800).to_bytes(4, "big")
    data[0xF0:0xF4] = (0x06004000).to_bytes(4, "big")
    return bytes(data)


def _shell_link() -> bytes:
    prefix = bytes.fromhex("4c0000000114020000000000c000000000000046")
    return prefix + (b"\x00" * 64)


def _candidate(root: Path) -> Path:
    candidate = root / "vdp1ex"
    candidate.mkdir()
    _write(candidate / "makefile", b"include ./OBJECTS\ninclude C:/SaturnOrbit/COMMON/mf_CMD\n")
    _write(candidate / "OBJECTS", b"TARGET = srk\nOBJS = CRT0.o main.o\n")
    _write(candidate / "run.bat", b"make\n")
    _write(candidate / "mf_CMD", b"CC = sh-elf-gcc\n")
    _write(candidate / "CRT0.S", b".section .text\n.global _start\n_start:\n")
    _write(candidate / "BART.LNK", b"SECTIONS { .text 0x06004000 : { *(.text) } }\n")
    _write(candidate / "MAKE_ELF.bat.lnk", _shell_link())
    _write(candidate / "main.c", b"int main(void) { return 0; }\n")
    _write(candidate / "smpc.c", b"unsigned read_pad(void) { return 0; }\n")
    _write(candidate / "conio.c", b"void draw_text(void) {}\n")
    _write(candidate / "IP.BIN", _ip_bin())
    _write(candidate / "asset.bin", b"\x00\x01\x02")
    return candidate


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.name: path.read_bytes()
        for path in sorted(root.iterdir())
        if path.is_file()
    }


class SaturnStandaloneTemplateTests(unittest.TestCase):
    def test_reports_hashes_roles_and_ip_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _candidate(Path(temp_dir))
            report = inspect_saturn_standalone_template(candidate)

            self.assertEqual(report.file_named("CRT0.S").role, "startup")
            self.assertEqual(report.file_named("main.c").role, "priority-source")
            self.assertEqual(report.file_named("IP.BIN").role, "ip-bin")
            self.assertEqual(
                report.file_named("asset.bin").sha256,
                sha256(b"\x00\x01\x02").hexdigest(),
            )
            metadata = dict(report.ip_metadata)
            self.assertEqual(metadata["hardware_id"], "SEGA SEGASATURN")
            self.assertEqual(metadata["product_number"], "T-0000G")
            self.assertEqual(metadata["game_title"], "SRK DIAGNOSTICS")
            self.assertEqual(metadata["first_read_address"], "0x06004000")

    def test_build_assets_are_text_and_shell_shortcuts_are_not_linkers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _candidate(Path(temp_dir))
            report = inspect_saturn_standalone_template(candidate)

            self.assertEqual(report.file_named("OBJECTS").role, "build-list")
            self.assertIn("CRT0.o", report.file_named("OBJECTS").text)
            self.assertEqual(report.file_named("run.bat").role, "script")
            self.assertEqual(report.file_named("run.bat").text, "make")
            self.assertEqual(report.file_named("mf_CMD").role, "makefile")
            self.assertIn("sh-elf-gcc", report.file_named("mf_CMD").text)
            self.assertEqual(report.file_named("BART.LNK").role, "linker")
            shortcut = report.file_named("MAKE_ELF.bat.lnk")
            self.assertEqual(shortcut.role, "shortcut")
            self.assertIsNone(shortcut.text)

    def test_text_capture_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _candidate(Path(temp_dir))
            (candidate / "main.c").write_text("\n".join(f"line {i}" for i in range(10)))

            report = inspect_saturn_standalone_template(candidate, max_text_lines=3)
            main = report.file_named("main.c")

            self.assertTrue(main.truncated)
            self.assertEqual(len(main.text.splitlines()), 3)

    def test_inspection_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _candidate(Path(temp_dir))
            before = _snapshot(candidate)

            inspect_saturn_standalone_template(candidate)

            self.assertEqual(_snapshot(candidate), before)

    def test_invalid_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaises(SaturnStandaloneTemplateError):
                inspect_saturn_standalone_template(missing)

    def test_cli_reports_read_only_inventory_and_source_excerpt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _candidate(Path(temp_dir))
            output = StringIO()

            with redirect_stdout(output):
                status = probe_main(["--candidate", str(candidate), "--max-lines", "20"])

            text = output.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("READ-ONLY", text)
            self.assertIn("SEGA SEGASATURN", text)
            self.assertIn("product_number: T-0000G", text)
            self.assertIn("===== makefile [makefile] =====", text)
            self.assertIn("===== OBJECTS [build-list] =====", text)
            self.assertIn("===== run.bat [script] =====", text)
            self.assertNotIn("===== MAKE_ELF.bat.lnk", text)
            self.assertIn("===== CRT0.S [startup] =====", text)
            self.assertIn("===== smpc.c [priority-source] =====", text)
            self.assertIn("No files were modified.", text)


if __name__ == "__main__":
    unittest.main()
