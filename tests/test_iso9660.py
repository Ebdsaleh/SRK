"""Tests for source-agnostic ISO-9660 filesystem access."""

import unittest

from rikai_kotoba.core.iso9660 import ISO9660PathError, ISO9660Reader


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
        self.user_sector_calls = []

    def read_user_sector(self, lba):
        self.user_sector_calls.append(lba)
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


class ISO9660ReaderTests(unittest.TestCase):
    def test_lists_root_and_strips_numeric_version_suffix(self):
        reader = ISO9660Reader(_make_source())
        entries = reader.list_root_directory()
        self.assertEqual(
            [entry.name for entry in entries],
            ["HELLO.TXT", "SUBDIR", "AUDIO.BIN"],
        )
        self.assertEqual(entries[0].raw_name, "HELLO.TXT;1")

    def test_reads_file_using_logical_source(self):
        source = _make_source()
        reader = ISO9660Reader(source)
        self.assertEqual(reader.read_file("/HELLO.TXT"), b"hello")
        self.assertIn(30, source.user_sector_calls)

    def test_resolves_nested_paths_case_insensitively(self):
        reader = ISO9660Reader(_make_source())
        entry = reader.get_entry("/subdir/nested.dat")
        self.assertEqual(entry.lba, 31)
        self.assertEqual(reader.read_file(entry), b"nest")

    def test_reads_extent_across_multiple_sectors(self):
        reader = ISO9660Reader(_make_source())
        data = reader.read_file("/AUDIO.BIN")
        self.assertEqual(data[:SECTOR], b"A" * SECTOR)
        self.assertEqual(data[SECTOR:], b"B" * (3000 - SECTOR))

    def test_walk_returns_nested_files(self):
        reader = ISO9660Reader(_make_source())
        paths = [path for path, _ in reader.walk()]
        self.assertEqual(
            paths,
            ["/HELLO.TXT", "/SUBDIR", "/SUBDIR/NESTED.DAT", "/AUDIO.BIN"],
        )

    def test_rejects_relative_parent_components(self):
        reader = ISO9660Reader(_make_source())
        with self.assertRaises(ISO9660PathError):
            reader.get_entry("/SUBDIR/../HELLO.TXT")


if __name__ == "__main__":
    unittest.main()
