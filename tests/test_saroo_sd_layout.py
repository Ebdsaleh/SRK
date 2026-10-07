from __future__ import annotations

import contextlib
from hashlib import sha256
import io
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.cli import main as srk_cli_main
from rikai_kotoba.hardware.saturn.saroo.sd_layout import (
    SAROO_SD_LAYOUT_LEGACY,
    SAROO_SD_LAYOUT_MIXED,
    SAROO_SD_LAYOUT_MODERN,
    SAROO_SD_LAYOUT_UNRECOGNIZED,
    SarooSdLayoutError,
    inspect_saroo_sd_layout,
)


class SarooSdLayoutTests(unittest.TestCase):
    def test_modern_layout_is_detected_and_firmware_is_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saroo = root / "SAROO"
            saroo.mkdir()
            payload = b"modern-saturn-firmware"
            (saroo / "ssfirm.bin").write_bytes(payload)
            (saroo / "mcuapp.bin").write_bytes(b"mcu")
            (saroo / "saroocfg.txt").write_text("# config\n", encoding="utf-8")
            (saroo / "ISO").mkdir()
            (saroo / "update").mkdir()

            report = inspect_saroo_sd_layout(root)

            self.assertEqual(report.layout, SAROO_SD_LAYOUT_MODERN)
            self.assertTrue(report.recognized)
            self.assertEqual(len(report.firmware_files), 1)
            self.assertEqual(report.firmware_files[0].relative_path, "SAROO/ssfirm.bin")
            self.assertEqual(report.firmware_files[0].size, len(payload))
            self.assertEqual(report.firmware_files[0].sha256, sha256(payload).hexdigest())
            self.assertTrue(report.saroo_directory_present)
            self.assertTrue(report.mcuapp_present)
            self.assertTrue(report.config_present)
            self.assertTrue(report.iso_directory_present)
            self.assertTrue(report.update_directory_present)
            self.assertEqual(report.warnings, ())

    def test_legacy_root_ramimage_layout_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = b"legacy-saturn-firmware"
            (root / "ramimage.bin").write_bytes(payload)

            report = inspect_saroo_sd_layout(root)

            self.assertEqual(report.layout, SAROO_SD_LAYOUT_LEGACY)
            self.assertTrue(report.recognized)
            self.assertEqual(report.firmware_files[0].relative_path, "ramimage.bin")
            self.assertEqual(report.firmware_files[0].sha256, sha256(payload).hexdigest())

    def test_mixed_layout_is_reported_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saroo = root / "SAROO"
            saroo.mkdir()
            (saroo / "ssfirm.bin").write_bytes(b"modern")
            (root / "ramimage.bin").write_bytes(b"legacy")

            report = inspect_saroo_sd_layout(root)

            self.assertEqual(report.layout, SAROO_SD_LAYOUT_MIXED)
            self.assertFalse(report.recognized)
            self.assertEqual(len(report.firmware_files), 2)
            self.assertTrue(report.warnings)

    def test_unrecognized_layout_is_reported_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "keep.txt"
            marker.write_bytes(b"unchanged")
            before_entries = sorted(path.name for path in root.iterdir())

            report = inspect_saroo_sd_layout(root)

            self.assertEqual(report.layout, SAROO_SD_LAYOUT_UNRECOGNIZED)
            self.assertFalse(report.recognized)
            self.assertEqual(report.firmware_files, ())
            self.assertTrue(report.warnings)
            self.assertEqual(marker.read_bytes(), b"unchanged")
            self.assertEqual(sorted(path.name for path in root.iterdir()), before_entries)

    def test_case_insensitive_documented_names_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saroo = root / "saroo"
            saroo.mkdir()
            (saroo / "SSFIRM.BIN").write_bytes(b"firmware")
            (saroo / "iso").mkdir()
            (saroo / "UPDATE").mkdir()

            report = inspect_saroo_sd_layout(root)

            self.assertEqual(report.layout, SAROO_SD_LAYOUT_MODERN)
            self.assertTrue(report.iso_directory_present)
            self.assertTrue(report.update_directory_present)

    def test_missing_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            with self.assertRaisesRegex(SarooSdLayoutError, "not a directory"):
                inspect_saroo_sd_layout(missing)

    def test_cli_prints_read_only_modern_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saroo = root / "SAROO"
            saroo.mkdir()
            (saroo / "ssfirm.bin").write_bytes(b"firmware")

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = srk_cli_main(["inspect-saroo-sd", str(root)])

            self.assertEqual(status, 0)
            rendered = output.getvalue()
            self.assertIn("Layout          : modern", rendered)
            self.assertIn("SAROO/ssfirm.bin", rendered)
            self.assertIn("No files were modified.", rendered)


if __name__ == "__main__":
    unittest.main()
