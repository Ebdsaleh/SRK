"""Tests for ranking local standalone Sega Saturn project candidates."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.standalone_candidates import (
    SaturnStandaloneCandidateError,
    inspect_saturn_standalone_candidates,
)
from rikai_kotoba.tools.saturn_standalone_candidate_probe import main as probe_main


def _touch(path: Path, data: bytes = b"test\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _root(base: Path) -> Path:
    root = base / "Saturn-Dev"

    _touch(root / "SaturnOrbit" / "SGL_302j" / "LIB_ELF" / "LIBSGL.A")
    _touch(root / "SaturnOrbit" / "COMMON" / "cinit.o")
    _touch(root / "SaturnOrbit" / "SGL_302j" / "LIB_ELF" / "sglarea.o")

    example = root / "SaturnOrbit-Inspect" / "payload" / "app" / "EXAMPLES" / "Demo"
    _touch(example / "IP.BIN", b"SEGA SEGASATURN")
    _touch(example / "main.c", b"int main(void) { return 0; }\n")
    _touch(example / "saturn.ld", b"SECTIONS {}\n")
    _touch(
        example / "Makefile",
        b"CC=sh-elf-gcc\nall:\n\tmkisofs -generic-boot IP.BIN -o demo.iso cd\n",
    )

    generic = root / "SaturnOrbit" / "SH_ELF" / "Samples" / "EVB7045" / "app1"
    _touch(generic / "main.c", b"int main(void) { return 0; }\n")
    _touch(generic / "makefile", b"CC=sh-elf-gcc\n")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class SaturnStandaloneCandidateTests(unittest.TestCase):
    def test_detects_lib_elf_and_ranks_bootable_example_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _root(Path(temp_dir))
            report = inspect_saturn_standalone_candidates(root)

            self.assertEqual(len(report.libraries), 1)
            self.assertEqual(report.libraries[0].name, "LIBSGL.A")
            self.assertEqual({path.name.casefold() for path in report.support_objects}, {"cinit.o", "sglarea.o"})
            self.assertGreaterEqual(len(report.candidates), 2)
            self.assertEqual(report.candidates[0].directory.name, "Demo")
            self.assertIsNotNone(report.candidates[0].ip_bin)
            self.assertIn("iso-build-command", report.candidates[0].evidence)
            self.assertIn("generic-sh-evaluation-sample", report.candidates[1].evidence)
            self.assertGreater(report.candidates[0].score, report.candidates[1].score)

    def test_candidate_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _root(Path(temp_dir))
            for index in range(5):
                candidate = root / "EXAMPLES" / f"Demo{index}"
                _touch(candidate / "main.c")
                _touch(candidate / "Makefile", b"CC=sh-elf-gcc\n")

            report = inspect_saturn_standalone_candidates(root, candidate_limit=3)
            self.assertEqual(len(report.candidates), 3)

    def test_probe_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _root(Path(temp_dir))
            before = _snapshot(root)

            inspect_saturn_standalone_candidates(root)

            self.assertEqual(_snapshot(root), before)

    def test_cli_reports_candidate_evidence_without_building(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _root(Path(temp_dir))
            output = StringIO()

            with redirect_stdout(output):
                status = probe_main(["--saturn-root", str(root), "--limit", "4"])

            text = output.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("READ-ONLY", text)
            self.assertIn("LIBSGL.A", text)
            self.assertIn("local-ip.bin", text)
            self.assertIn("iso-build-command", text)
            self.assertIn("No files were modified.", text)

    def test_invalid_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaises(SaturnStandaloneCandidateError):
                inspect_saturn_standalone_candidates(missing)


if __name__ == "__main__":
    unittest.main()
