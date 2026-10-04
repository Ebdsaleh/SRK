# src/rikai_kotoba/core/iso_reader.py


import struct
from rikai_kotoba.core.sector_io import SectorReader


class ISOReader:
    def __init__(self, bin_path):
        self.reader = SectorReader(bin_path)
        self.root_extent_lba = 0
        self.root_data_length = 0
        self._parse_pvd()

    def _parse_pvd(self):
        """
        Locates and parses the ISO-9660 Primary Volume Descriptor at LBA 16.
        """
        # PVD is located at logical sector (LBA) 16
        pvd_data = self.reader.read_lba(16)

        # Verify standard ISO-9660 indentifier "CD001" at offset 1
        identifier = pvd_data[1:6].decode("ascii", errors="ignore")
        if identifier != "CD001":
            raise ValueError(f"[-] Invalid ISO-9660 filesystem: Expected 'CD001', found '{identifier}'")

        # Root Directory Record starts at offset 156 within the PVD
        # Let's extract the root directory extent location and length
        root_dir_record = pvd_data[156:190]
        
        # Extent Location (LBA of root directory) is at offset 2 (4 bytes little-endian, followed by 4 bytes big-endian)
        self.root_extent_lba = struct.unpack("<I", root_dir_record[2:6])[0]
        
        # Data Length of the root directory is at offset 10 (4 bytes little-endian)
        self.root_data_length = struct.unpack("<I", root_dir_record[10:14])[0]

    def list_root_directory(self):
        """
        Parses the root directory table to list internal files and folders.
        """
        files = []
        # Read the sectors belonging to the root directory
        sectors_to_read = (self.root_data_length + 2047) // 2048
        root_bytes = bytearray()
        
        for i in range(sectors_to_read):
            root_bytes.extend(self.reader.read_lba(self.root_extent_lba + i))
            
        offset = 0
        while offset < self.root_data_length:
            record_len = root_bytes[offset]
            if record_len == 0:
                # Padded bytes to the end of the sector
                # Move to the start of the next sector boundary
                offset = ((offset + 2047) // 2048) * 2048
                continue
                
            # Parse individual directory record fields
            extent_lba = struct.unpack("<I", root_bytes[offset+2:offset+6])[0]
            data_length = struct.unpack("<I", root_bytes[offset+10:offset+14])[0]
            flags = root_bytes[offset+25]
            name_len = root_bytes[offset+32]
            
            if name_len > 0:
                name = root_bytes[offset+33 : offset+33+name_len].decode("ascii", errors="ignore")
                # Clean up ISO specific filename padding (e.g., ";1" version suffixes)
                is_directory = (flags & 2) != 0
                
                files.append({
                    "name": name,
                    "lba": extent_lba,
                    "size": data_length,
                    "is_dir": is_directory
                })
                
            offset += record_len
            
        return files
