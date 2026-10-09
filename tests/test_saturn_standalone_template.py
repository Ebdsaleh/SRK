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


def _ip_bin() -> bytes:
    data = bytearray(2048)
    fields = (
        (0, 16, "SEGA SEGASATURN"),
        (16, 32, "SEGA ENTERPRISES"),
        (32, 48, "CD-1/1"),
        (48, 56, "JTUB"),
        (56, 72, "J"),
        (72, 112, "SRK DIAGNOSTICS"),
        (112, 128, "V0.001"),
        (128, 144, "20261009"),
        (144, 160, "T-0000G"),
    )
    for start, end, text in fields:
        data[start:end] = text.encode("ascii").ljust(end - start, b" ")
    return bytes(data)


def _candidate(root: Path) -> Path:
    candidate = root / "vdp1ex"
    candidate.mkdir()
    _write(candidate / "makefile", b"CC=sh-elf-gcc\nall:\n\t$(CC) main.c\n")
    _write(candidate / "CRT0.S", b".section .text\n.global _start\n_start:\n")
    _write(candidate / "saturn.ld", b"SECTIONS { .text 0x06004000 : { *(.text) } }\n")
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
            self.assertEqual(metadata["game_title"], "SRK DIAGNOSTICS")

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
            self.assertIn("===== makefile [makefile] =====", text)
            self.assertIn("===== CRT0.S [startup] =====", text)
            self.assertIn("===== smpc.c [priority-source] =====", text)
            self.assertIn("No files were modified.", text)


if __name__ == "__main__":
    unittest.main()
