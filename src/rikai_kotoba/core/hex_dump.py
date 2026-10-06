"""Generic hexadecimal dump formatting for SRK.

This module contains no platform- or game-specific knowledge.  It formats
bytes in the familiar ``offset: hex  ASCII`` form used by SRK research tools.
"""

from __future__ import annotations

import os
from typing import Iterator


DEFAULT_WIDTH = 16


def format_hexdump_line(
    offset: int,
    chunk: bytes,
    *,
    width: int = DEFAULT_WIDTH,
) -> str:
    """Format one hexadecimal dump line.

    ``offset`` is the logical byte offset displayed at the start of the line.
    ``chunk`` may contain at most ``width`` bytes.
    """

    if offset < 0:
        raise ValueError("offset must be non-negative")
    if width <= 0:
        raise ValueError("width must be positive")
    if len(chunk) > width:
        raise ValueError("chunk is larger than the requested dump width")

    hex_str = " ".join(f"{byte:02X}" for byte in chunk)
    ascii_str = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
    return f"{offset:08X}: {hex_str:<{width * 3}} {ascii_str}"


def iter_hexdump_lines(
    data: bytes,
    *,
    start_offset: int = 0,
    width: int = DEFAULT_WIDTH,
) -> Iterator[str]:
    """Yield formatted dump lines for ``data``."""

    if start_offset < 0:
        raise ValueError("start_offset must be non-negative")
    if width <= 0:
        raise ValueError("width must be positive")

    for index in range(0, len(data), width):
        yield format_hexdump_line(
            start_offset + index,
            data[index : index + width],
            width=width,
        )


def hexdump_text(
    data: bytes,
    *,
    start_offset: int = 0,
    width: int = DEFAULT_WIDTH,
) -> str:
    """Return a complete hexadecimal dump string."""

    lines = list(
        iter_hexdump_lines(data, start_offset=start_offset, width=width)
    )
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def write_hexdump(
    data: bytes,
    output_path: os.PathLike[str] | str,
    *,
    overwrite: bool = False,
    start_offset: int = 0,
    width: int = DEFAULT_WIDTH,
) -> str:
    """Write a hexadecimal dump without silently replacing an existing file."""

    path = os.path.abspath(os.fspath(output_path))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    mode = "w" if overwrite else "x"
    with open(path, mode, encoding="utf-8", newline="\n") as handle:
        for line in iter_hexdump_lines(
            data,
            start_offset=start_offset,
            width=width,
        ):
            handle.write(line)
            handle.write("\n")

    return path
