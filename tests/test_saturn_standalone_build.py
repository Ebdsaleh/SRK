"""Tests for Python-native standalone Saturn build orchestration."""

from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from rikai_kotoba.formats.saturn.mode1_image import verify_mode1_bin_against_iso
from rikai_kotoba.formats.saturn.packaged_pcm import PACKAGED_PCM_FILENAME
from rikai_kotoba.hardware.saturn.standalone_build import (
    SaturnStandaloneBuildError,
    build_saturn_standalone_project,
)
from rikai_kotoba.hardware.saturn.standalone_project import (
    prepare_saturn_standalone_project,
)


ISO_SECTOR = 2048


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


def _iso_record(name: str, lba: int, size: int, *, is_dir: bool = False) -> bytes:
    if name == ".":
        identifier = b"\x00"
    elif name == "..":
        identifier = b"\x01"
    else:
        identifier = name.encode("ascii")

    length = 33 + len(identifier)
    if length % 2:
        length += 1
    record = bytearray(length)
    record[0] = length
    record[2:6] = lba.to_bytes(4, "little")
    record[6:10] = lba.to_bytes(4, "big")
    record[10:14] = size.to_bytes(4, "little")
    record[14:18] = size.to_bytes(4, "big")
    record[25] = 0x02 if is_dir else 0x00
    record[28:30] = (1).to_bytes(2, "little")
    record[30:32] = (1).to_bytes(2, "big")
    record[32] = len(identifier)
    record[33 : 33 + len(identifier)] = identifier
    return bytes(record)


def _write_test_iso(path: Path, payload: bytes, *, corrupt_payload: bool = False) -> None:
    root_lba = 20
    payload_lba = 21
    total_sectors = 22
    image = bytearray(total_sectors * ISO_SECTOR)

    root_record = _iso_record(".", root_lba, ISO_SECTOR, is_dir=True)
    pvd = bytearray(ISO_SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01
    pvd[156 : 156 + len(root_record)] = root_record
    image[16 * ISO_SECTOR : 17 * ISO_SECTOR] = pvd

    root = bytearray(ISO_SECTOR)
    records = (
        root_record,
        _iso_record("..", root_lba, ISO_SECTOR, is_dir=True),
        _iso_record(f"{PACKAGED_PCM_FILENAME};1", payload_lba, len(payload)),
    )
    offset = 0
    for record in records:
        root[offset : offset + len(record)] = record
        offset += len(record)
    image[root_lba * ISO_SECTOR : (root_lba + 1) * ISO_SECTOR] = root

    packaged = bytearray(payload)
    if corrupt_payload:
        packaged[-1] ^= 0x01
    start = payload_lba * ISO_SECTOR
    image[start : start + len(packaged)] = packaged
    path.write_bytes(image)


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
    def __init__(self, *, corrupt_iso_payload: bool = False):
        self.calls = []
        self.corrupt_iso_payload = corrupt_iso_payload

    def __call__(self, argv, **kwargs):
        self.calls.append((tuple(argv), dict(kwargs)))
        root = Path(kwargs["cwd"])
        self._assert_direct(kwargs)

        if "-o" in argv:
            output = root / argv[argv.index("-o") + 1]
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.suffix.casefold() == ".iso":
                payload = (root / "cd" / PACKAGED_PCM_FILENAME).read_bytes()
                _write_test_iso(
                    output,
                    payload,
                    corrupt_payload=self.corrupt_iso_payload,
                )
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
            payload_before = (project / "cd" / PACKAGED_PCM_FILENAME).read_bytes()
            runner = _SuccessfulRunner()

            result = build_saturn_standalone_project(project, _runner=runner)

            self.assertTrue(result.successful)
            self.assertEqual(len(runner.calls), 13)
            self.assertTrue(
                any("src/srk_diag_vdp1.c" in call[0] for call in runner.calls)
            )
            self.assertTrue(
                any("src/srk_diag_audio.c" in call[0] for call in runner.calls)
            )
            self.assertTrue(
                any("src/srk_saturn_audio.c" in call[0] for call in runner.calls)
            )
            self.assertTrue((project / "build" / "srk_diag.bin").is_file())
            iso = project / "build" / "srk_diag.iso"
            self.assertTrue(iso.is_file())
            self.assertTrue((project / "cd" / "0.bin").is_file())
            self.assertEqual(
                (project / "cd" / PACKAGED_PCM_FILENAME).read_bytes(),
                payload_before,
            )
            deploy = project / "build" / "SRK-Diagnostics"
            raw = deploy / "SRK-Diagnostics.bin"
            cue = deploy / "SRK-Diagnostics.cue"
            self.assertTrue(raw.is_file())
            self.assertTrue(cue.is_file())
            sector_count = iso.stat().st_size // ISO_SECTOR
            self.assertEqual(verify_mode1_bin_against_iso(iso, raw), sector_count)
            self.assertEqual(raw.stat().st_size, sector_count * 2352)
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
            self.assertEqual(len(report["artifacts"]), 7)
            packaged = report["packaged_pcm"]
            self.assertEqual(packaged["project_path"], f"cd/{PACKAGED_PCM_FILENAME}")
            self.assertEqual(packaged["iso_path"], f"/{PACKAGED_PCM_FILENAME};1")
            self.assertEqual(packaged["iso_extent_lba"], 21)
            self.assertEqual(packaged["size"], len(payload_before))
            self.assertTrue(packaged["verified_against_project"])
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
            self.assertIn("verify packaged PCM in ISO", result.log_path.read_text(encoding="utf-8"))

    def test_iso_payload_mismatch_fails_before_mode1_publication(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = _prepared_project(Path(temp_dir))
            payload_before = (project / "cd" / PACKAGED_PCM_FILENAME).read_bytes()

            result = build_saturn_standalone_project(
                project,
                _runner=_SuccessfulRunner(corrupt_iso_payload=True),
            )

            self.assertFalse(result.successful)
            self.assertEqual(
                (project / "cd" / PACKAGED_PCM_FILENAME).read_bytes(),
                payload_before,
            )
            self.assertFalse((project / "build" / "SRK-Diagnostics").exists())
            report = json.loads(result.report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["successful"])
            self.assertNotIn("packaged_pcm", report)
            log = result.log_path.read_text(encoding="utf-8")
            self.assertIn("verify packaged PCM in ISO", log)
            self.assertIn("do not match the generated project payload", log)

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
