# src/rikai_kotoba/core/cue_parser.py

import re
import os

def parse_cue_sheet(cue_path):
    """
    Parses a Sega Saturn .cue file to extract track numbers, types, 
    and their corresponding file paths.
    """
    tracks = []
    current_file = None
    
    if not os.path.exists(cue_path):
        raise FileNotFoundError(f"[-] Error: Could not find cue file at '{cue_path}'")

    with open(cue_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            
            # Match FILE lines (e.g., FILE "soul_hackers.bin" BINARY)
            file_match = re.search(r'^FILE\s+"([^"]+)"', line, re.IGNORECASE)
            if file_match:
                current_file = file_match.group(1)
                continue
                
            # Match TRACK lines (e.g., TRACK 01 MODE1/2352)
            track_match = re.search(r'^TRACK\s+(\d+)\s+([A-Z0-9_/]+)', line, re.IGNORECASE)
            if track_match:
                track_num = int(track_match.group(1))
                track_type = track_match.group(2)
                
                tracks.append({
                    "track": track_num,
                    "type": track_type,
                    "file": current_file
                })
                
    return tracks

def get_primary_data_track(path):
    """
    Accepts either a .cue sheet or a direct raw binary file (.bin/.img).
    If a binary file is passed directly, it returns it. If a cue is passed,
    it parses the track sheet to find the primary data track.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"[-] Error: Path not found at '{path}'")

    # If the user passed a raw binary file directly, accept it
    if path.lower().endswith(('.bin', '.img', '.iso', '.raw')):
        return path

    # Otherwise, parse it as a .cue sheet
    tracks = parse_cue_sheet(path)
    for track in tracks:
        if "MODE" in track["type"].upper():
            bin_file = track["file"]
            if bin_file and not os.path.exists(bin_file):
                resolved_path = os.path.join(os.path.dirname(path), bin_file)
                if os.path.exists(resolved_path):
                    return resolved_path
            return bin_file
            
    raise ValueError(f"[-] Error: No valid data track found in {path}")
