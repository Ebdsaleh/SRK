# SRK (Salix Rikai Kotoba)

A modular text extraction and localization framework for retro game formats, starting with the Sega Saturn.

## Features
* **Raw Disc & CUE Parsing:** Handles 2352-byte raw sector bin/cue layouts and extracts Saturn boot metadata (`IP.BIN`).
* **ISO-9660 Filesystem Walker:** Parses Primary Volume Descriptors and lists internal directories, file LBA offsets, and byte sizes.
* **Extensible Architecture:** Designed to scale easily to other retro disc platforms.

## Installation & Usage

1. Create and activate your virtual environment:
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate  # On Windows PowerShell / Command Prompt

2. Upgrade pip and install dependencies:
   python -m pip install --upgrade pip
   pip install -r requirements.txt

3. Inspect a Saturn disc image:
   python src/rikai_kotoba/cli.py inspect-saturn path/to/game.cue

4. List internal filesystem files:
   python src/rikai_kotoba/cli.py list-files path/to/game.cue
---

### 2. `requirements.txt`
```text
# SRK (Rikai Kotoba) Dependencies
# Currently pure Python standard library for core binary parsers.

