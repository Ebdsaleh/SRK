"""Sega Saturn IP.BIN boot-header parsing.

The parser operates on SRK's logical read-only disc sources rather than on a
hardcoded raw-sector reader.  It therefore works with both standalone images
and CUE-backed multi-track discs.
"""

from __future__ import annotations

import os
from typing import Dict, Union

from rikai_kotoba.core.disc_source import open_disc_source


SATURN_IP_HEADER_SIZE = 160


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
    if len(data) < SATURN_IP_HEADER_SIZE:
        raise SaturnIPBinError(
            f"Saturn boot sector is too short: {len(data)} bytes"
        )
    return data


def _decode_ascii_field(data: bytes) -> str:
    return data.decode("ascii", errors="replace").rstrip("\x00 ").strip()


def parse_ip_bin(
    source: Union[object, os.PathLike[str], str],
) -> Dict[str, str]:
    """Parse the 160-byte Saturn IP.BIN header from logical LBA 0.

    ``source`` may be an already-open SRK disc source or a supported image/CUE
    path. Path inputs are opened read-only through ``open_disc_source``.
    """

    if isinstance(source, (str, os.PathLike)):
        source = open_disc_source(source)

    sector_data = _read_user_sector(source, 0)

    return {
        "hardware_id": _decode_ascii_field(sector_data[0:16]),
        "maker_id": _decode_ascii_field(sector_data[16:32]),
        "device_info": _decode_ascii_field(sector_data[32:48]),
        "area_symbols": _decode_ascii_field(sector_data[48:56]),
        "peripherals": _decode_ascii_field(sector_data[56:72]),
        "game_title": _decode_ascii_field(sector_data[72:112]),
        "game_version": _decode_ascii_field(sector_data[112:128]),
        "game_date": _decode_ascii_field(sector_data[128:144]),
        "game_serial": _decode_ascii_field(sector_data[144:160]),
    }
