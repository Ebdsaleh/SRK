# src/rikai_kotoba/core/sector_io.py

import os

SECTOR_SIZE_RAW = 2352
SECTOR_DATA_SIZE = 2048
RAW_DATA_OFFSET = 16  # Skipping sync and header bytes in Mode 1 / Mode 2 raw sectors

class SectorReader:
    def __init__(self, bin_path):
        self.bin_path = bin_path
        if not os.path.exists(bin_path):
            raise FileNotFoundError(f"Binary file not found: {bin_path}")
        self.file_size = os.path.getsize(bin_path)
        self.total_sectors = self.file_size // SECTOR_SIZE_RAW

    def read_lba(self, lba):
        """Reads user data (2048 bytes) from a specific Logical Block Address (Sector)."""
        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(f"LBA {lba} out of bounds (Total sectors: {self.total_sectors})")
        
        offset = (lba * SECTOR_SIZE_RAW) + RAW_DATA_OFFSET
        with open(self.bin_path, "rb") as f:
            f.seek(offset)
            return f.read(SECTOR_DATA_SIZE)

    def read_raw_sector(self, lba):
        """Reads the full 2352-byte raw sector including headers."""
        if lba < 0 or lba >= self.total_sectors:
            raise ValueError(f"LBA {lba} out of bounds")
            
        offset = lba * SECTOR_SIZE_RAW
        with open(self.bin_path, "rb") as f:
            f.seek(offset)
            return f.read(SECTOR_SIZE_RAW)
