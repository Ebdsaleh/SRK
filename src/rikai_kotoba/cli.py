# src/rikai_kotoba/cli.py


import argparse
import sys
import os

# Ensure src is discoverable if run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rikai_kotoba.core.cue_parser import get_primary_data_track
from rikai_kotoba.formats.saturn.ip_bin import parse_ip_bin
from rikai_kotoba.core.iso_reader import ISOReader

def main():
    parser = argparse.ArgumentParser(description="SRK (Rikai Kotoba) - Retro Game Localization Toolkit")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Saturn Inspect Command
    saturn_parser = subparsers.add_parser("inspect-saturn", help="Inspect a Sega Saturn CUE/BIN disc image")
    saturn_parser.add_argument("path", type=str, help="Path to the game .cue or raw .bin file")

    # List Files Command
    list_parser = subparsers.add_parser("list-files", help="List internal files on an ISO-9660 disc image")
    list_parser.add_argument("path", type=str, help="Path to the game .cue or raw .bin file")

    args = parser.parse_args()

    try:
        bin_path = get_primary_data_track(args.path)
    except Exception as e:
        print(f"[-] Error resolving data track: {e}")
        sys.exit(1)

    if args.command == "inspect-saturn":
        print(f"[*] Analyzing Sega Saturn image: {args.path}")
        print(f"[+] Found primary data track binary: {bin_path}")
        try:
            metadata = parse_ip_bin(bin_path)
            print("\n--- Saturn Disc Metadata ---")
            for key, val in metadata.items():
                print(f"  {key.replace('_', ' ').title():<15}: {val}")
        except Exception as e:
            print(f"[-] Error during inspection: {e}")
            sys.exit(1)

    elif args.command == "list-files":
        print(f"[*] Scanning ISO-9660 filesystem in: {bin_path}")
        try:
            iso = ISOReader(bin_path)
            files = iso.list_root_directory()
            print(f"\n--- Root Directory Contents ({len(files)} entries) ---")
            print(f"{'Type':<6} {'Start LBA':<12} {'Size (Bytes)':<14} {'Name'}")
            print("-" * 55)
            for f in files:
                f_type = "DIR" if f["is_dir"] else "FILE"
                print(f"{f_type:<6} {f['lba']:<12} {f['size']:<14} {f['name']}")
        except Exception as e:
            print(f"[-] Error parsing ISO filesystem: {e}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
