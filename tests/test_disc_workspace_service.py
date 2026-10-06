"""Synthetic-disc tests for the application-layer workspace service."""

import os
import tempfile
import unittest

from rikai_kotoba.application.disc_workspace import DiscWorkspaceService


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
    record[25] = 0x02 if is_dir else 0
    record[28:30] = (1).to_bytes(2, "little")
    record[30:32] = (1).to_bytes(2, "big")
    record[32] = len(identifier)
    record[33 : 33 + len(identifier)] = identifier
    return bytes(record)


def _make_iso(path):
    image = bytearray(SECTOR * 40)
    root_lba = 20

    pvd = bytearray(SECTOR)
    pvd[0] = 0x01
    pvd[1:6] = b"CD001"
    pvd[6] = 0x01
    root_record = _record(".", root_lba, SECTOR, True)
    pvd[156 : 156 + len(root_record)] = root_record
    image[16 * SECTOR : 17 * SECTOR] = pvd

    root = bytearray(SECTOR)
    records = [
        _record(".", root_lba, SECTOR, True),
        _record("..", root_lba, SECTOR, True),
        _record("HELLO.TXT;1", 30, 5, False),
    ]
    offset = 0
    for record in records:
        root[offset : offset + len(record)] = record
        offset += len(record)
    image[root_lba * SECTOR : (root_lba + 1) * SECTOR] = root
    image[30 * SECTOR : 30 * SECTOR + 5] = b"hello"

    with open(path, "wb") as handle:
        handle.write(image)


class DiscWorkspaceServiceTests(unittest.TestCase):
    def test_opens_synthetic_iso_and_exposes_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image = os.path.join(temp_dir, "sample.iso")
            _make_iso(image)
            service = DiscWorkspaceService()

            snapshot = service.open_source(image)

            self.assertEqual(snapshot.base_name, "sample")
            self.assertEqual(snapshot.source_kind, "MODE1/2048")
            self.assertEqual(snapshot.file_count, 1)
            self.assertEqual(snapshot.directory_count, 0)
            self.assertEqual(snapshot.entries[0].path, "/HELLO.TXT")
            self.assertEqual(service.read_file("/HELLO.TXT"), b"hello")


if __name__ == "__main__":
    unittest.main()
