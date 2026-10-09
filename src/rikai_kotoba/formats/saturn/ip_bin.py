"""Sega Saturn IP.BIN (Initial Program) System ID parsing.

The parser operates on SRK's logical read-only disc sources rather than on a
hardcoded raw-sector reader.  It therefore works with both standalone images
and CUE-backed multi-track discs.

The first 0x100 bytes are the Saturn System ID.  Keep these offsets separate
from Dreamcast/Katana IP.BIN layouts: Saturn stores product/version/date/device
fields at 0x20-0x3F and the game title begins at 0x60.
"""

from __future__ import annotations

import os
from typing import Dict, Union

from rikai_kotoba.core.disc_source import open_disc_source


SATURN_SYSTEM_ID_SIZE = 0x100


class SaturnIPBinError(Exception):
    """Raised when a Saturn boot header cannot be read safely."""


def _read_user_sector(source: object, lba: int) -> bytes:
    reader = getattr(source, "read_user_sector", None)
    if reader is None:
        reader = getattr(source, "read_lba", None)
    if reader is None:
        raise TypeError(
            "Saturn IP.BIN source must provide read_user_sector(lba) "
            "or read_lba(lba)"
        )

    data = reader(lba)
    if len(data) < SATURN_SYSTEM_ID_SIZE:
        raise SaturnIPBinError(
            f"Saturn System ID is too short: {len(data)} bytes; "
            f"need at least {SATURN_SYSTEM_ID_SIZE}"
        )
    return data


def _decode_ascii_field(data: bytes) -> str:
    return data.decode("ascii", errors="replace").rstrip("\x00 ").strip()


def _u32be_hex(data: bytes) -> str:
    return f"0x{int.from_bytes(data, byteorder='big', signed=False):08X}"


def parse_saturn_system_id(data: bytes) -> Dict[str, str]:
    """Parse the 0x100-byte Saturn System ID from ``data``.

    Numeric control fields are returned as fixed-width hexadecimal strings so
    the public result remains a string dictionary while preserving exact raw
    values useful to diagnostics and standalone-build review.

    ``game_serial`` remains as a compatibility alias for ``product_number``.
    """

    if len(data) < SATURN_SYSTEM_ID_SIZE:
        raise SaturnIPBinError(
            f"Saturn System ID is too short: {len(data)} bytes; "
            f"need at least {SATURN_SYSTEM_ID_SIZE}"
        )

    product_number = _decode_ascii_field(data[0x20:0x2A])

    return {
        "hardware_id": _decode_ascii_field(data[0x00:0x10]),
        "maker_id": _decode_ascii_field(data[0x10:0x20]),
        "product_number": product_number,
        "game_serial": product_number,
        "game_version": _decode_ascii_field(data[0x2A:0x30]),
        "game_date": _decode_ascii_field(data[0x30:0x38]),
        "device_info": _decode_ascii_field(data[0x38:0x40]),
        "area_symbols": _decode_ascii_field(data[0x40:0x4A]),
        "peripherals": _decode_ascii_field(data[0x50:0x60]),
        "game_title": _decode_ascii_field(data[0x60:0xD0]),
        "ip_size": _u32be_hex(data[0xE0:0xE4]),
        "master_stack": _u32be_hex(data[0xE8:0xEC]),
        "slave_stack": _u32be_hex(data[0xEC:0xF0]),
        "first_read_address": _u32be_hex(data[0xF0:0xF4]),
        "first_read_size": _u32be_hex(data[0xF4:0xF8]),
    }


def parse_ip_bin(
    source: Union[object, os.PathLike[str], str],
) -> Dict[str, str]:
    """Parse Saturn System ID metadata from logical LBA 0.

    ``source`` may be an already-open SRK disc source or a supported image/CUE
    path. Path inputs are opened read-only through ``open_disc_source``.
    """

    if isinstance(source, (str, os.PathLike)):
        source = open_disc_source(source)

    sector_data = _read_user_sector(source, 0)
    return parse_saturn_system_id(sector_data)
