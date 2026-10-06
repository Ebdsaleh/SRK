"""Generic, read-only optical-disc data track access for SRK.

The source image is never opened writable. Any code that intends to modify a
disc must first create a separate writable copy through ``create_output_copy``.

This module intentionally contains no game-specific knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
from typing import BinaryIO, Optional


ISO_USER_DATA_SIZE = 2048
RAW_SECTOR_SIZE = 2352
ISO_PVD_LBA = 16
ISO_PVD_MAGIC = b"CD001"


class DiscImageError(Exception):
    """Base error for generic disc-image operations."""


class UnsupportedDiscGeometryError(DiscImageError):
    """Raised when SRK cannot identify the image's sector geometry."""


class UnsafeOutputPathError(DiscImageError):
    """Raised when an output path could overwrite the source image."""


@dataclass(frozen=True)
class SectorGeometry:
    """Physical sector layout for a data track."""

    name: str
    sector_size: int
    user_data_offset: int
    user_data_size: int = ISO_USER_DATA_SIZE

    def physical_offset(self, lba: int) -> int:
        if lba < 0:
            raise ValueError("LBA must be non-negative")
        return (lba * self.sector_size) + self.user_data_offset


MODE1_2048 = SectorGeometry("MODE1/2048", 2048, 0)
MODE1_2352 = SectorGeometry("MODE1/2352", 2352, 16)
MODE2_2352_FORM1 = SectorGeometry("MODE2/2352", 2352, 24)

SUPPORTED_GEOMETRIES = (
    MODE1_2048,
    MODE1_2352,
    MODE2_2352_FORM1,
)


def _canonical_path(path: os.PathLike[str] | str) -> str:
    """Return a platform-aware canonical path suitable for safety checks."""

    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def paths_refer_to_same_file(
    first: os.PathLike[str] | str,
    second: os.PathLike[str] | str,
) -> bool:
    """Return True if two paths resolve to the same filesystem target.

    ``os.path.samefile`` is used when both paths exist; otherwise a canonical
    path comparison is used so a not-yet-created output path is still checked.
    """

    first_s = os.fspath(first)
    second_s = os.fspath(second)

    if os.path.exists(first_s) and os.path.exists(second_s):
        try:
            return os.path.samefile(first_s, second_s)
        except OSError:
            pass

    return _canonical_path(first_s) == _canonical_path(second_s)


class DiscImage:
    """Read-only view of a single optical-disc data track.

    ``DiscImage`` detects 2048-byte Mode 1, 2352-byte raw Mode 1, and
    2352-byte raw Mode 2/Form 1 layouts from the ISO-9660 Primary Volume
    Descriptor. It never opens ``source_path`` in a writable mode.
    """

    def __init__(
        self,
        source_path: os.PathLike[str] | str,
        geometry: Optional[SectorGeometry] = None,
    ) -> None:
        self.source_path = os.path.abspath(os.fspath(source_path))
        if not os.path.isfile(self.source_path):
            raise FileNotFoundError(f"Disc image not found: {self.source_path}")

        self.file_size = os.path.getsize(self.source_path)
        self.geometry = geometry or self.detect_geometry(self.source_path)
        self.total_sectors = self.file_size // self.geometry.sector_size

    @staticmethod
    def _has_pvd_magic(handle: BinaryIO, geometry: SectorGeometry) -> bool:
        offset = geometry.physical_offset(ISO_PVD_LBA)
        handle.seek(offset)
        descriptor = handle.read(6)
        return len(descriptor) == 6 and descriptor[1:6] == ISO_PVD_MAGIC

    @classmethod
    def detect_geometry(
        cls, source_path: os.PathLike[str] | str
    ) -> SectorGeometry:
        """Detect supported sector geometry without modifying the image."""

        path = os.path.abspath(os.fspath(source_path))
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Disc image not found: {path}")

        with open(path, "rb") as handle:
            for geometry in SUPPORTED_GEOMETRIES:
                if cls._has_pvd_magic(handle, geometry):
                    return geometry

        raise UnsupportedDiscGeometryError(
            "Unable to locate an ISO-9660 Primary Volume Descriptor using "
            "supported 2048/2352-byte sector layouts: " + path
        )

    def read_lba(self, lba: int) -> bytes:
        """Read one 2048-byte user-data sector from ``lba``."""

        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(
                f"LBA {lba} out of bounds (total sectors: {self.total_sectors})"
            )

        with open(self.source_path, "rb") as handle:
            handle.seek(self.geometry.physical_offset(lba))
            data = handle.read(self.geometry.user_data_size)

        if len(data) != self.geometry.user_data_size:
            raise DiscImageError(
                f"Short read at LBA {lba}: expected "
                f"{self.geometry.user_data_size} bytes, got {len(data)}"
            )
        return data

    def read_lbas(self, start_lba: int, count: int) -> bytes:
        """Read ``count`` consecutive logical user-data sectors."""

        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return b""
        if start_lba < 0 or start_lba + count > self.total_sectors:
            raise ValueError(
                f"LBA range {start_lba}..{start_lba + count - 1} out of bounds "
                f"(total sectors: {self.total_sectors})"
            )

        chunks = bytearray()
        with open(self.source_path, "rb") as handle:
            for lba in range(start_lba, start_lba + count):
                handle.seek(self.geometry.physical_offset(lba))
                data = handle.read(self.geometry.user_data_size)
                if len(data) != self.geometry.user_data_size:
                    raise DiscImageError(
                        f"Short read at LBA {lba}: expected "
                        f"{self.geometry.user_data_size} bytes, got {len(data)}"
                    )
                chunks.extend(data)
        return bytes(chunks)

    def read_file_extent(self, start_lba: int, size: int) -> bytes:
        """Read an ISO file extent and trim final-sector padding."""

        if size < 0:
            raise ValueError("size must be non-negative")
        if size == 0:
            return b""

        count = (
            size + self.geometry.user_data_size - 1
        ) // self.geometry.user_data_size
        return self.read_lbas(start_lba, count)[:size]

    def assert_safe_output_path(self, output_path: os.PathLike[str] | str) -> str:
        """Validate that an output cannot resolve to the source image."""

        output = os.path.abspath(os.fspath(output_path))
        if paths_refer_to_same_file(self.source_path, output):
            raise UnsafeOutputPathError(
                "Refusing to use the source image as an output. "
                "SRK source images are read-only by policy."
            )
        return output

    def create_output_copy(
        self,
        output_path: os.PathLike[str] | str,
        *,
        overwrite: bool = False,
    ) -> str:
        """Create a separate writable copy while leaving the source untouched.

        The returned path is the new copy. Existing output files are rejected
        unless ``overwrite=True``. The source is *always* rejected as output.
        """

        output = self.assert_safe_output_path(output_path)

        if os.path.exists(output) and not overwrite:
            raise FileExistsError(f"Output already exists: {output}")

        parent = os.path.dirname(output)
        if parent:
            os.makedirs(parent, exist_ok=True)

        shutil.copy2(self.source_path, output)
        return output
