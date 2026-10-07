"""Synthetic tests for generic Saturn/SAROO capture artifacts."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.capture import (
    CaptureStore,
    CapturedRegion,
    MemoryRange,
    load_manifest,
    verify_capture,
)


class SarooCaptureTests(unittest.TestCase):
    def test_memory_range_validates_32_bit_bounds(self):
        region = MemoryRange(0x06000000, 0x1000, "work_ram")
        self.assertEqual(region.end_address_exclusive, 0x06001000)
        self.assertTrue(region.contains(0x06000000))
        self.assertFalse(region.contains(0x06001000))
        with self.assertRaises(ValueError):
            MemoryRange(-1, 1)
        with self.assertRaises(ValueError):
            MemoryRange(0xFFFFFFFF, 2)
        with self.assertRaises(ValueError):
            MemoryRange(0x06000000, 0)

    def test_captured_region_requires_exact_requested_byte_count(self):
        memory_range = MemoryRange(0x06000000, 4, "sample")
        captured = CapturedRegion(memory_range, b"ABCD")
        self.assertEqual(
            captured.sha256,
            hashlib.sha256(b"ABCD").hexdigest(),
        )
        with self.assertRaises(ValueError):
            CapturedRegion(memory_range, b"ABC")

    def test_capture_store_publishes_manifest_and_region_atomically(self):
        timestamp = datetime(2026, 10, 7, 2, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Dumps" / "SAROO"
            store = CaptureStore(root)
            first = CapturedRegion(MemoryRange(0x06000000, 4, "work ram low"), b"LOW!")
            second = CapturedRegion(MemoryRange(0x06100000, 4, "work ram high"), b"HIGH")

            artifact = store.save(
                "before dialogue",
                (first, second),
                captured_at=timestamp,
                session_label="synthetic session",
            )

            self.assertEqual(
                artifact.directory.name,
                "20261007T023000Z_before_dialogue",
            )
            self.assertTrue(artifact.manifest_path.is_file())
            self.assertEqual(tuple(path.read_bytes() for path in artifact.region_paths), (b"LOW!", b"HIGH"))

            manifest = load_manifest(artifact.directory)
            self.assertEqual(manifest["platform"], "sega-saturn")
            self.assertEqual(manifest["transport"], "saroo")
            self.assertEqual(manifest["checkpoint"], "before dialogue")
            self.assertEqual(manifest["session_label"], "synthetic session")
            self.assertEqual(manifest["captured_at_utc"], "2026-10-07T02:30:00Z")
            self.assertEqual(len(manifest["regions"]), 2)
            self.assertTrue(verify_capture(artifact.directory).valid)
            self.assertFalse(any(path.name.startswith(".srk-capture-") for path in root.iterdir()))

    def test_existing_capture_directory_is_never_overwritten(self):
        timestamp = datetime(2026, 10, 7, 2, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            store = CaptureStore(temporary)
            region = CapturedRegion(MemoryRange(0x06000000, 4, "sample"), b"DATA")
            first = store.save("checkpoint", (region,), captured_at=timestamp)
            second = store.save("checkpoint", (region,), captured_at=timestamp)

            self.assertEqual(first.directory.name, "20261007T023000Z_checkpoint")
            self.assertEqual(second.directory.name, "20261007T023000Z_checkpoint_01")
            self.assertEqual(first.region_paths[0].read_bytes(), b"DATA")
            self.assertEqual(second.region_paths[0].read_bytes(), b"DATA")

    def test_capture_verification_detects_tampering(self):
        timestamp = datetime(2026, 10, 7, 2, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            store = CaptureStore(temporary)
            region = CapturedRegion(MemoryRange(0x06000000, 4, "sample"), b"DATA")
            artifact = store.save("checkpoint", (region,), captured_at=timestamp)
            artifact.region_paths[0].write_bytes(b"FAIL")

            verification = verify_capture(artifact.directory)
            self.assertFalse(verification.valid)
            self.assertTrue(any("SHA-256 mismatch" in error for error in verification.errors))
            with self.assertRaisesRegex(Exception, "SHA-256 mismatch"):
                verification.require_valid()

    def test_manifest_rejects_unknown_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "capture.json").write_text(
                json.dumps({"schema": "unknown", "version": 1, "regions": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Exception, "schema"):
                load_manifest(directory)


if __name__ == "__main__":
    unittest.main()
