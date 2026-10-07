"""Synthetic tests for SRK's exact provenance correlation engine."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.core.correlation import correlate_file_to_memory_dump


class CorrelationTests(unittest.TestCase):
    def _write_pair(self, source: bytes, memory: bytes):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        source_path = root / "source.bin"
        memory_path = root / "memory.bin"
        source_path.write_bytes(source)
        memory_path.write_bytes(memory)
        return temporary, source_path, memory_path

    def test_adjacent_exact_chunks_coalesce_into_provenance_run(self):
        source = b"ABCDEFGH" + b"IJKLMNOP" + b"QRSTUVWX" + b"YZ012345"
        memory = b"xxxx" + b"IJKLMNOP" + b"QRSTUVWX" + b"yyyy"
        temporary, source_path, memory_path = self._write_pair(source, memory)
        with temporary:
            report = correlate_file_to_memory_dump(
                source_path,
                memory_path,
                memory_base_address=0x06000000,
                chunk_size=8,
                minimum_chunk_size=4,
            )

        self.assertEqual(report.scanned_chunks, 4)
        self.assertEqual(report.matched_chunks, 2)
        self.assertEqual(report.ambiguous_chunks, 0)
        self.assertEqual(len(report.runs), 1)
        run = report.runs[0]
        self.assertEqual(run.source_offset, 8)
        self.assertEqual(run.memory_offset, 4)
        self.assertEqual(run.memory_address, 0x06000004)
        self.assertEqual(run.length, 16)
        self.assertEqual(run.chunk_count, 2)
        self.assertEqual(report.longest_run, run)

    def test_final_partial_chunk_is_correlated_when_above_minimum(self):
        source = b"ABCDEFGH" + b"IJKLMNOP" + b"QRST"
        memory = b"--" + source + b"--"
        temporary, source_path, memory_path = self._write_pair(source, memory)
        with temporary:
            report = correlate_file_to_memory_dump(
                source_path,
                memory_path,
                memory_base_address=0x00200000,
                chunk_size=8,
                minimum_chunk_size=4,
            )

        self.assertEqual(report.scanned_chunks, 3)
        self.assertEqual(report.matched_chunks, 3)
        self.assertEqual(len(report.runs), 1)
        self.assertEqual(report.runs[0].length, len(source))
        self.assertEqual(report.runs[0].memory_address, 0x00200002)

    def test_highly_repeated_chunks_are_reported_as_ambiguous_not_matches(self):
        source = b"00000000" + b"UNIQUE!!"
        memory = (b"00000000" * 5) + b"UNIQUE!!"
        temporary, source_path, memory_path = self._write_pair(source, memory)
        with temporary:
            report = correlate_file_to_memory_dump(
                source_path,
                memory_path,
                memory_base_address=0,
                chunk_size=8,
                minimum_chunk_size=8,
                maximum_occurrences_per_chunk=2,
            )

        self.assertEqual(report.scanned_chunks, 2)
        self.assertEqual(report.ambiguous_chunks, 1)
        self.assertEqual(report.matched_chunks, 1)
        self.assertEqual(len(report.runs), 1)
        self.assertEqual(report.runs[0].source_offset, 8)

    def test_report_hashes_both_inputs(self):
        source = b"ABCDEFGH"
        memory = b"--ABCDEFGH--"
        temporary, source_path, memory_path = self._write_pair(source, memory)
        with temporary:
            report = correlate_file_to_memory_dump(
                source_path,
                memory_path,
                memory_base_address=0x06000000,
                chunk_size=8,
                minimum_chunk_size=8,
            )

        self.assertEqual(report.source_sha256, hashlib.sha256(source).hexdigest())
        self.assertEqual(report.memory_dump_sha256, hashlib.sha256(memory).hexdigest())

    def test_memory_dump_must_fit_32_bit_address_space(self):
        temporary, source_path, memory_path = self._write_pair(b"ABCD", b"12345678")
        with temporary:
            with self.assertRaises(ValueError):
                correlate_file_to_memory_dump(
                    source_path,
                    memory_path,
                    memory_base_address=0xFFFFFFFC,
                    chunk_size=4,
                    minimum_chunk_size=4,
                )


if __name__ == "__main__":
    unittest.main()
