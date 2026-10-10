"""Tests for the bounded Stage 6B mixed-object-format link probe."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.standalone_build import SaturnStage6BDependencies
from rikai_kotoba.tools.saturn_stage6b_link_probe import (
    SaturnStage6BLinkProbeError,
    _mixed_link_tail,
    _validate_cdc_coff_archive,
    _validate_gfs_elf_archive,
)
from tests.binary_fixtures import coff_sh_fixture


def _ar_member(name: str, payload: bytes) -> bytes:
    raw_name = (name + "/").encode("ascii").ljust(16, b" ")
    header = b"".join(
        (
            raw_name,
            b"0".ljust(12, b" "),
            b"0".ljust(6, b" "),
            b"0".ljust(6, b" "),
            b"100644".ljust(8, b" "),
            str(len(payload)).encode("ascii").ljust(10, b" "),
            b"`\n",
        )
    )
    assert len(header) == 60
    return header + payload + (b"\n" if len(payload) & 1 else b"")


def _archive(name: str, payload: bytes) -> bytes:
    return b"!<arch>\n" + _ar_member(name, payload)


def _elf32_sh_rel() -> bytes:
    data = bytearray(64)
    data[0:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 2
    data[6] = 1
    data[16:18] = (1).to_bytes(2, "big")
    data[18:20] = (42).to_bytes(2, "big")
    return bytes(data)


class SaturnStage6BLinkProbeTests(unittest.TestCase):
    def test_mixed_link_tail_scopes_only_cdc_as_coff_and_uses_dedicated_support(self):
        deps = SaturnStage6BDependencies(
            include_dir=Path("INCLUDE"),
            gfs_header=Path("INCLUDE/SEGA_GFS.H"),
            gfs_library=Path("LIB_ELF/sega_gfs.a"),
            cdc_library=Path("LIB_ELF/SEGA_CDC.A"),
            dma_library=Path("LIB_ELF/sega_dma.a"),
            csh_library=Path("LIB_ELF/sega_csh.a"),
            int_library=Path("LIB_ELF/sega_int.a"),
        )

        tail = _mixed_link_tail(deps)

        self.assertEqual(
            tail,
            (
                str(Path("LIB_ELF") / "sega_gfs.a"),
                "-Wl,--format=coff-sh",
                str(Path("LIB_ELF") / "SEGA_CDC.A"),
                "-Wl,--format=elf32-sh",
                str(Path("LIB_ELF") / "sega_dma.a"),
                str(Path("LIB_ELF") / "sega_csh.a"),
                str(Path("LIB_ELF") / "sega_int.a"),
                "-lgcc",
            ),
        )

    def test_gfs_validator_accepts_elf32_big_endian_sh_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sega_gfs.a"
            path.write_bytes(_archive("gfs.o", _elf32_sh_rel()))
            summary = _validate_gfs_elf_archive(path)
            self.assertEqual(summary.object_format, "elf32-sh")
            self.assertEqual(summary.payload_members, 1)
            self.assertIn("ELF32 big-endian SH", summary.detail)

    def test_cdc_validator_accepts_hitachi_sh_big_endian_coff_archive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SEGA_CDC.A"
            path.write_bytes(_archive("cdc_cmn.o", coff_sh_fixture()))
            summary = _validate_cdc_coff_archive(path)
            self.assertEqual(summary.object_format, "coff-sh")
            self.assertEqual(summary.payload_members, 1)
            self.assertIn("magic 0x0500", summary.detail)

    def test_cdc_validator_rejects_elf_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "SEGA_CDC.A"
            path.write_bytes(_archive("cdc_cmn.o", _elf32_sh_rel()))
            with self.assertRaises(SaturnStage6BLinkProbeError):
                _validate_cdc_coff_archive(path)


if __name__ == "__main__":
    unittest.main()
