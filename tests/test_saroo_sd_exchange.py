"""Synthetic tests for SAROO SD-file capture exchange primitives."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    CaptureStore,
    MemoryRange,
    SAROO_SD_WRITE_CHUNK_SIZE,
    import_raw_sd_dump,
    plan_sd_write_chunks,
    total_planned_bytes,
    verify_capture,
)


class SarooSdExchangeTests(unittest.TestCase):
    def test_one_megabyte_range_uses_sixteen_verified_64k_chunks(self):
        memory_range = MemoryRange(0x06000000, 0x00100000, "work_ram_high")
        chunks = plan_sd_write_chunks(memory_range)

        self.assertEqual(SAROO_SD_WRITE_CHUNK_SIZE, 0x10000)
        self.assertEqual(len(chunks), 16)
        self.assertEqual(total_planned_bytes(chunks), memory_range.size)
        self.assertEqual(chunks[0].source_address, 0x06000000)
        self.assertEqual(chunks[0].file_offset, 0)
        self.assertEqual(chunks[0].upstream_write_offset, -1)
        self.assertTrue(chunks[0].truncate)
        self.assertEqual(chunks[1].source_address, 0x06010000)
        self.assertEqual(chunks[1].file_offset, 0x10000)
        self.assertEqual(chunks[1].upstream_write_offset, 0x10000)
        self.assertFalse(chunks[1].truncate)
        self.assertEqual(chunks[-1].source_address, 0x060F0000)
        self.assertEqual(chunks[-1].file_offset, 0x000F0000)

    def test_partial_final_chunk_preserves_exact_requested_size(self):
        memory_range = MemoryRange(0x00200000, 0x10020, "partial")
        chunks = plan_sd_write_chunks(memory_range)

        self.assertEqual([chunk.size for chunk in chunks], [0x10000, 0x20])
        self.assertEqual(total_planned_bytes(chunks), 0x10020)

    def test_plan_rejects_chunk_size_above_verified_staging_size(self):
        with self.assertRaisesRegex(ValueError, "verified SAROO staging size"):
            plan_sd_write_chunks(
                MemoryRange(0x06000000, 0x20000),
                chunk_size=SAROO_SD_WRITE_CHUNK_SIZE + 1,
            )

    def test_raw_sd_dump_import_creates_verified_capture_without_modifying_source(self):
        payload = bytes((index * 17) & 0xFF for index in range(0x2000))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "wram_h.bin"
            source.write_bytes(payload)
            before = source.read_bytes()
            store = CaptureStore(temp / "captures")

            artifact = import_raw_sd_dump(
                source,
                base_address=0x06000000,
                checkpoint="title-screen",
                store=store,
                label="work_ram_high",
                session_label="synthetic",
                expected_size=len(payload),
            )

            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(verify_capture(artifact.directory).valid)
            manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["checkpoint"], "title-screen")
            self.assertEqual(manifest["session_label"], "synthetic")
            self.assertEqual(manifest["regions"][0]["start_address"], 0x06000000)
            self.assertEqual(manifest["regions"][0]["size"], len(payload))
            self.assertEqual(artifact.region_paths[0].read_bytes(), payload)

    def test_raw_sd_dump_import_rejects_wrong_expected_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "dump.bin"
            source.write_bytes(b"1234")
            with self.assertRaisesRegex(ValueError, "expected size"):
                import_raw_sd_dump(
                    source,
                    base_address=0x00200000,
                    checkpoint="test",
                    store=CaptureStore(temp / "captures"),
                    expected_size=8,
                )

    def test_raw_sd_dump_import_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "empty.bin"
            source.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "empty"):
                import_raw_sd_dump(
                    source,
                    base_address=0x00200000,
                    checkpoint="test",
                    store=CaptureStore(temp / "captures"),
                )


if __name__ == "__main__":
    unittest.main()
