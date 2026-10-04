# src/rikai_kotoba/formats/saturn/ip_bin.py


import os
from rikai_kotoba.core.sector_io import SectorReader

def parse_ip_bin(bin_path):
    """
    Parses the Saturn IP.BIN boot header from LBA 0 of the raw disc image.
    """
    reader = SectorReader(bin_path)
    # LBA 0 contains the hardware header
    sector_data = reader.read_lba(0)
    
    # Saturn boot header structure mapping
    hardware_id = sector_data[0:16].decode("ascii", errors="ignore").strip()
    maker_id = sector_data[16:32].decode("ascii", errors="ignore").strip()
    device_info = sector_data[32:48].decode("ascii", errors="ignore").strip()
    area_symbols = sector_data[48:56].decode("ascii", errors="ignore").strip()
    peripherals = sector_data[56:72].decode("ascii", errors="ignore").strip()
    game_title = sector_data[72:112].decode("ascii", errors="ignore").strip()
    game_version = sector_data[112:128].decode("ascii", errors="ignore").strip()
    game_date = sector_data[128:144].decode("ascii", errors="ignore").strip()
    game_serial = sector_data[144:160].decode("ascii", errors="ignore").strip()
    
    metadata = {
        "hardware_id": hardware_id,
        "maker_id": maker_id,
        "device_info": device_info,
        "area_symbols": area_symbols,
        "peripherals": peripherals,
        "game_title": game_title,
        "game_version": game_version,
        "game_date": game_date,
        "game_serial": game_serial
    }
    
    return metadata
