"""Create and verify single-track raw CD-ROM Mode 1 images.

SRK's standalone Saturn project is first assembled as a normal 2048-byte-sector
ISO9660 data track.  SAROO's documented image path is CUE/BIN, so this module
re-frames each ISO sector as a full 2352-byte CD-ROM Mode 1 sector and writes a
matching single-track CUE sheet.

The framing follows the standard Mode 1 layout:

    12 sync + 4 header + 2048 user + 4 EDC + 8 zero + 276 ECC = 2352

No source image is modified.  The converter always writes a new BIN/CUE pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile


ISO_USER_BYTES = 2048
RAW_SECTOR_BYTES = 2352
_SYNC = bytes((0x00, *([0xFF] * 10), 0x00))


class SaturnMode1ImageError(RuntimeError):
    """Raised when a Mode 1 image cannot be generated or verified safely."""


@dataclass(frozen=True)
class SaturnMode1ImageResult:
    iso_path: Path
    bin_path: Path
    cue_path: Path
    sector_count: int
    user_bytes: int
    raw_bytes: int


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _bcd(value: int) -> int:
    if value < 0 or value > 99:
        raise SaturnMode1ImageError(f"BCD value out of range: {value}")
    return ((value // 10) << 4) | (value % 10)


def _tables() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    ecc_f = [0] * 256
    ecc_b = [0] * 256
    edc = [0] * 256

    for value in range(256):
        doubled = (value << 1) ^ (0x11D if value & 0x80 else 0)
        doubled &= 0xFF
        ecc_f[value] = doubled
        ecc_b[value ^ doubled] = value

        crc = value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xD8018001 if crc & 1 else 0)
        edc[value] = crc & 0xFFFFFFFF

    return tuple(ecc_f), tuple(ecc_b), tuple(edc)


_ECC_F, _ECC_B, _EDC = _tables()


def _compute_edc(data: bytes | bytearray | memoryview) -> int:
    value = 0
    for byte in data:
        value = (value >> 8) ^ _EDC[(value ^ byte) & 0xFF]
    return value & 0xFFFFFFFF


def _compute_ecc_block(
    source: bytes | bytearray | memoryview,
    major_count: int,
    minor_count: int,
    major_mult: int,
    minor_inc: int,
) -> bytes:
    block_size = major_count * minor_count
    if len(source) < block_size:
        raise SaturnMode1ImageError("ECC source block is too small")

    output = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = 0
        ecc_b = 0

        for _ in range(minor_count):
            byte = source[index]
            index += minor_inc
            if index >= block_size:
                index -= block_size
            ecc_a ^= byte
            ecc_b ^= byte
            ecc_a = _ECC_F[ecc_a]

        ecc_a = _ECC_B[_ECC_F[ecc_a] ^ ecc_b]
        output[major] = ecc_a
        output[major + major_count] = ecc_a ^ ecc_b

    return bytes(output)


def encode_mode1_sector(user_data: bytes, lba: int) -> bytes:
    """Return one 2352-byte Mode 1 sector for a 2048-byte logical sector."""

    if len(user_data) != ISO_USER_BYTES:
        raise SaturnMode1ImageError(
            f"Mode 1 user sector must be {ISO_USER_BYTES} bytes, got {len(user_data)}"
        )
    if lba < 0:
        raise SaturnMode1ImageError("LBA must be non-negative")

    absolute_frame = lba + 150
    minute = absolute_frame // (60 * 75)
    remainder = absolute_frame % (60 * 75)
    second = remainder // 75
    frame = remainder % 75
    if minute > 99:
        raise SaturnMode1ImageError("LBA exceeds two-digit CD MSF range")

    sector = bytearray(RAW_SECTOR_BYTES)
    sector[0x000:0x00C] = _SYNC
    sector[0x00C] = _bcd(minute)
    sector[0x00D] = _bcd(second)
    sector[0x00E] = _bcd(frame)
    sector[0x00F] = 0x01
    sector[0x010:0x810] = user_data

    edc = _compute_edc(sector[0x000:0x810])
    sector[0x810:0x814] = edc.to_bytes(4, "little")
    sector[0x814:0x81C] = b"\x00" * 8

    # ECC-Q covers the already-written ECC-P bytes, so P must be generated first.
    sector[0x81C:0x8C8] = _compute_ecc_block(
        sector[0x00C:0x81C], 86, 24, 2, 86
    )
    sector[0x8C8:0x930] = _compute_ecc_block(
        sector[0x00C:0x8C8], 52, 43, 86, 88
    )
    return bytes(sector)


def verify_mode1_bin_against_iso(
    iso_path: os.PathLike[str] | str,
    bin_path: os.PathLike[str] | str,
) -> int:
    """Verify every raw sector exactly matches the ISO's Mode 1 framing."""

    iso = _canonical(iso_path)
    raw = _canonical(bin_path)
    if not iso.is_file():
        raise SaturnMode1ImageError(f"ISO source is not a file: {iso}")
    if not raw.is_file():
        raise SaturnMode1ImageError(f"raw BIN is not a file: {raw}")

    iso_size = iso.stat().st_size
    if iso_size == 0 or iso_size % ISO_USER_BYTES:
        raise SaturnMode1ImageError(
            f"ISO size must be a non-zero multiple of {ISO_USER_BYTES}: {iso_size}"
        )

    sectors = iso_size // ISO_USER_BYTES
    expected_raw_size = sectors * RAW_SECTOR_BYTES
    actual_raw_size = raw.stat().st_size
    if actual_raw_size != expected_raw_size:
        raise SaturnMode1ImageError(
            f"raw BIN size mismatch: expected {expected_raw_size}, got {actual_raw_size}"
        )

    with iso.open("rb") as iso_handle, raw.open("rb") as raw_handle:
        for lba in range(sectors):
            user_data = iso_handle.read(ISO_USER_BYTES)
            actual = raw_handle.read(RAW_SECTOR_BYTES)
            expected = encode_mode1_sector(user_data, lba)
            if actual != expected:
                raise SaturnMode1ImageError(
                    f"raw BIN sector {lba} failed Mode 1 EDC/ECC/header verification"
                )

    return sectors


def write_single_track_mode1_bin_cue(
    iso_path: os.PathLike[str] | str,
    bin_path: os.PathLike[str] | str,
    cue_path: os.PathLike[str] | str,
) -> SaturnMode1ImageResult:
    """Convert one 2048-byte-sector ISO into a new MODE1/2352 BIN/CUE pair."""

    iso = _canonical(iso_path)
    raw = _canonical(bin_path)
    cue = _canonical(cue_path)

    if not iso.is_file():
        raise SaturnMode1ImageError(f"ISO source is not a file: {iso}")
    if raw.exists():
        raise SaturnMode1ImageError(f"refusing to overwrite raw BIN: {raw}")
    if cue.exists():
        raise SaturnMode1ImageError(f"refusing to overwrite CUE: {cue}")
    if raw.parent != cue.parent:
        raise SaturnMode1ImageError("BIN and CUE must be written to the same directory")

    iso_size = iso.stat().st_size
    if iso_size == 0 or iso_size % ISO_USER_BYTES:
        raise SaturnMode1ImageError(
            f"ISO size must be a non-zero multiple of {ISO_USER_BYTES}: {iso_size}"
        )

    raw.parent.mkdir(parents=True, exist_ok=True)
    sector_count = iso_size // ISO_USER_BYTES
    fd, temp_name = tempfile.mkstemp(prefix=f".{raw.name}.", dir=str(raw.parent))
    os.close(fd)
    temp_raw = Path(temp_name)

    try:
        with iso.open("rb") as source, temp_raw.open("wb") as destination:
            for lba in range(sector_count):
                user_data = source.read(ISO_USER_BYTES)
                if len(user_data) != ISO_USER_BYTES:
                    raise SaturnMode1ImageError(
                        f"short ISO read at sector {lba}: {len(user_data)} bytes"
                    )
                destination.write(encode_mode1_sector(user_data, lba))
        temp_raw.replace(raw)

        cue_text = (
            f'FILE "{raw.name}" BINARY\r\n'
            "  TRACK 01 MODE1/2352\r\n"
            "    INDEX 01 00:00:00\r\n"
        )
        cue.write_bytes(cue_text.encode("ascii"))
        verified = verify_mode1_bin_against_iso(iso, raw)
        if verified != sector_count:
            raise SaturnMode1ImageError("raw BIN verification sector count mismatch")
    except Exception:
        temp_raw.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
        cue.unlink(missing_ok=True)
        raise

    return SaturnMode1ImageResult(
        iso_path=iso,
        bin_path=raw,
        cue_path=cue,
        sector_count=sector_count,
        user_bytes=iso_size,
        raw_bytes=raw.stat().st_size,
    )
