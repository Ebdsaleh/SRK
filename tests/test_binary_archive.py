"""Tests for Mjolnir's read-only generic binary/archive inspector."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.core.binary_archive import (
    BinaryArchiveError,
    inspect_binary,
)


def _ar_member(name: str, payload: bytes) -> bytes:
    header = (
        name.encode("ascii").ljust(16, b" ")
        + b"0".ljust(12, b" ")
        + b"0".ljust(6, b" ")
        + b"0".ljust(6, b" ")
        + b"100644".ljust(8, b" ")
        + str(len(payload)).encode("ascii").ljust(10, b" ")
        + b"`\n"
    )
    assert len(header) == 60
    pad = b"\n" if len(payload) & 1 else b""
    return header + payload + pad


def _elf32_sh_big_endian() -> bytes:
    data = bytearray(52)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 2
    data[6] = 1
    data[16:18] = (1).to_bytes(2, "big")
    data[18:20] = (42).to_bytes(2, "big")
    return bytes(data)


class BinaryArchiveTests(unittest.TestCase):
    def test_classic_ar_member_reports_offsets_hash_and_elf_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "libsample.a"
            path.write_bytes(b"!<arch>\n" + _ar_member("sample.o/", _elf32_sh_big_endian()))

            report = inspect_binary(path)

            self.assertEqual(report.container_kind, "unix-ar")
            self.assertEqual(len(report.members), 1)
            member = report.members[0]
            self.assertEqual(member.name, "sample.o")
            self.assertEqual(member.header_offset, 8)
            self.assertEqual(member.data_offset, 68)
            self.assertEqual(member.size, 52)
            self.assertEqual(member.signature.kind, "elf")
            self.assertIn("ELF32 big-endian REL", member.signature.detail)
            self.assertIn("machine=SH(42)", member.signature.detail)

    def test_gnu_string_table_resolves_long_member_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "liblong.a"
            names = b"very-long-object-name-for-srk.o/\n"
            payload = _elf32_sh_big_endian()
            path.write_bytes(
                b"!<arch>\n"
                + _ar_member("//", names)
                + _ar_member("/0", payload)
            )

            report = inspect_binary(path)

            self.assertEqual(len(report.members), 2)
            self.assertTrue(report.members[0].metadata)
            self.assertEqual(report.members[1].name, "very-long-object-name-for-srk.o")
            self.assertFalse(report.members[1].metadata)

    def test_bsd_long_member_name_is_removed_from_logical_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "libbsd.a"
            long_name = b"very_long_member_name.o"
            object_bytes = _elf32_sh_big_endian()
            stored = long_name + object_bytes
            path.write_bytes(
                b"!<arch>\n"
                + _ar_member(f"#1/{len(long_name)}", stored)
            )

            report = inspect_binary(path)
            member = report.members[0]

            self.assertEqual(member.name, long_name.decode("ascii"))
            self.assertEqual(member.stored_size, len(stored))
            self.assertEqual(member.size, len(object_bytes))
            self.assertEqual(member.signature.kind, "elf")

    def test_unknown_binary_is_reported_without_guessing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mystery.bin"
            path.write_bytes(b"SEGA-UNKNOWN\x00\x01\x02\x03")

            report = inspect_binary(path)

            self.assertEqual(report.container_kind, "raw/unknown")
            self.assertEqual(report.signature.kind, "unknown")
            self.assertEqual(report.members, ())
            self.assertIn("53 45 47 41", report.signature.prefix_hex)

    def test_truncated_ar_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.a"
            path.write_bytes(b"!<arch>\n" + b"short")

            with self.assertRaises(BinaryArchiveError):
                inspect_binary(path)


if __name__ == "__main__":
    unittest.main()
