"""Tests for safe, generic ISO-9660 extraction."""

import hashlib
import os
import tempfile
import unittest

from rikai_kotoba.core.iso9660 import ISO9660Reader
from rikai_kotoba.core.safe_extractor import ISOExtractor, UnsafeExtractionPathError


SECTOR = 2048


def _record(name, lba, size, is_dir=False):
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


class MemorySectorSource:
    def __init__(self):
        self.sectors = {}
        self.fail_lbas = set()

    def read_user_sector(self, lba):
        if lba in self.fail_lbas:
            raise RuntimeError(f"blocked logical extent at LBA {lba}")
        return self.sectors.get(lba, bytes(SECTOR))


def _make_source():
    source = MemorySectorSource()
    root_lba = 20
    root_size = SECTOR

    pvd = bytearray(SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01
    root_record = _record(".", root_lba, root_size, True)
    pvd[156 : 156 + len(root_record)] = root_record
    source.sectors[16] = bytes(pvd)

    root = bytearray(SECTOR)
    records = [
        _record(".", root_lba, root_size, True),
        _record("..", root_lba, root_size, True),
        _record("HELLO.TXT;1", 30, 5, False),
        _record("SUBDIR", 21, SECTOR, True),
        _record("AUDIO.BIN;1", 40, 3000, False),
    ]
    offset = 0
    for record in records:
        root[offset : offset + len(record)] = record
        offset += len(record)
    source.sectors[root_lba] = bytes(root)

    subdir = bytearray(SECTOR)
    records = [
        _record(".", 21, SECTOR, True),
        _record("..", root_lba, root_size, True),
        _record("NESTED.DAT;1", 31, 4, False),
    ]
    offset = 0
    for record in records:
        subdir[offset : offset + len(record)] = record
        offset += len(record)
    source.sectors[21] = bytes(subdir)

    source.sectors[30] = b"hello" + bytes(SECTOR - 5)
    source.sectors[31] = b"nest" + bytes(SECTOR - 4)
    source.sectors[40] = b"A" * SECTOR
    source.sectors[41] = b"B" * SECTOR
    return source


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


class ISOExtractorTests(unittest.TestCase):
    def test_extracts_reachable_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            extractor = ISOExtractor(ISO9660Reader(_make_source()))
            report = extractor.extract_all(temp_dir)

            self.assertEqual(report.extracted_count, 3)
            self.assertEqual(report.directory_count, 1)
            self.assertEqual(report.error_count, 0)
            self.assertEqual(_read(os.path.join(temp_dir, "HELLO.TXT")), b"hello")
            self.assertEqual(
                _read(os.path.join(temp_dir, "SUBDIR", "NESTED.DAT")), b"nest"
            )

    def test_existing_output_is_skipped_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "HELLO.TXT")
            with open(target, "wb") as handle:
                handle.write(b"keep me")

            report = ISOExtractor(ISO9660Reader(_make_source())).extract_all(temp_dir)
            item = next(item for item in report.items if item.iso_path == "/HELLO.TXT")

            self.assertEqual(item.status, "skipped_existing")
            self.assertEqual(_read(target), b"keep me")

    def test_explicit_overwrite_replaces_existing_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = os.path.join(temp_dir, "HELLO.TXT")
            with open(target, "wb") as handle:
                handle.write(b"old")

            item = ISOExtractor(ISO9660Reader(_make_source())).extract_file(
                "/HELLO.TXT", temp_dir, overwrite=True
            )

            self.assertEqual(item.status, "extracted")
            self.assertEqual(_read(target), b"hello")

    def test_source_collision_is_refused_and_hash_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "HELLO.TXT")
            with open(source_path, "wb") as handle:
                handle.write(b"immutable source bytes")

            source = _make_source()
            source.source_path = source_path
            extractor = ISOExtractor(ISO9660Reader(source))
            before = hashlib.sha256(_read(source_path)).hexdigest()

            with self.assertRaises(UnsafeExtractionPathError):
                extractor.extract_file("/HELLO.TXT", temp_dir, overwrite=True)

            after = hashlib.sha256(_read(source_path)).hexdigest()
            self.assertEqual(before, after)

    def test_source_read_error_never_creates_empty_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _make_source()
            source.fail_lbas.add(40)
            report = ISOExtractor(ISO9660Reader(source)).extract_all(temp_dir)
            item = next(item for item in report.items if item.iso_path == "/AUDIO.BIN")

            self.assertEqual(item.status, "error")
            self.assertEqual(item.error_type, "RuntimeError")
            self.assertFalse(os.path.exists(os.path.join(temp_dir, "AUDIO.BIN")))
            self.assertEqual(report.extracted_count, 2)
            self.assertEqual(report.error_count, 1)

    def test_rejects_traversal_and_nonportable_components(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            extractor = ISOExtractor(ISO9660Reader(_make_source()))

            bad_paths = (
                "/../EVIL.BIN",
                "/A/../../EVIL.BIN",
                "/C:/EVIL.BIN",
                "/NUL",
                "/BAD?.BIN",
            )
            for bad_path in bad_paths:
                with self.subTest(path=bad_path):
                    with self.assertRaises(UnsafeExtractionPathError):
                        extractor.resolve_destination(bad_path, temp_dir)


if __name__ == "__main__":
    unittest.main()
