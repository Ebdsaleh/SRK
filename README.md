# SRK — Salix Rikai Kotoba

SRK is a modular retro-disc localization and reverse-engineering toolkit written in Python. The project begins with Sega Saturn support, while keeping the core disc, ISO-9660, extraction, and hex tooling platform- and game-agnostic.

SRK is currently alpha software. The public repository intentionally contains no game-specific offsets, patches, extracted game data, or disc images.

## Core goals

- Treat original disc images as **read-only sources**.
- Model CUE-backed multi-track discs as one logical LBA space.
- Read ISO-9660 files without loading complete disc images into memory.
- Surface unsupported/non-data extents explicitly instead of silently creating partial or zero-byte output.
- Keep platform-specific format knowledge separate from generic disc infrastructure.
- Keep title-specific research outside the reusable public core.

## Current capabilities

### Generic disc layer

- Standalone `BIN`, `IMG`, `ISO`, and `RAW` image access.
- Automatic detection of supported 2048-byte and 2352-byte data-sector layouts.
- CUE parsing with multi-file logical-LBA mapping.
- Explicit AUDIO-track detection.
- ISO-9660 directory walking, path lookup, and file reads.
- Safe extraction with traversal protection and source-collision checks.
- Standard hex rendering and file output.

### Sega Saturn

- Saturn `IP.BIN` boot-header inspection from logical LBA 0.
- Saturn-specific code lives under `rikai_kotoba.formats.saturn` rather than in the generic core.

### Mjolnir

Mjolnir is SRK's interactive disc/hex research utility. It can:

- discover CUE sheets and standalone images;
- prefer a CUE over the physical track files it references;
- list the reachable ISO-9660 filesystem;
- select and dump individual files as hex;
- create one complete filesystem hex blob;
- create structured filesystem extractions;
- create portable ZIP dumps;
- resolve output conflicts with **Cancel / Auto-rename / Overwrite** behavior.

Mjolnir accepts an image file or a directory supplied by the user. It does not assume a repository-local game directory.

## Installation

SRK requires Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the virtual environment, then install SRK in editable mode:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

For the optional pytest development dependency:

```bash
python -m pip install -e .[dev]
```

The package installs two console commands:

```text
srk
srk-mjolnir
```

You can also run the package directly:

```bash
python -m rikai_kotoba
```

## CLI examples

List the complete reachable ISO-9660 tree:

```bash
srk list-files /path/to/disc.cue
```

List only the ISO root directory:

```bash
srk list-files /path/to/disc.cue --root-only
```

Inspect Sega Saturn boot metadata:

```bash
srk inspect-saturn /path/to/disc.cue
```

Safely extract the reachable filesystem:

```bash
srk extract /path/to/disc.cue /path/to/output
```

Extract one ISO path:

```bash
srk extract /path/to/disc.cue /path/to/output --file /EXAMPLE.BIN
```

## Mjolnir examples

Open one disc immediately:

```bash
srk-mjolnir /path/to/disc.cue
```

Search a directory recursively and write generated artifacts to a separate workspace:

```bash
srk-mjolnir /path/to/images --output-dir /path/to/workspace
```

With no source argument, option 0 searches the current working directory:

```bash
srk-mjolnir
```

Generated structured dumps and portable ZIPs are placed beneath `extracted_output/` inside the selected output workspace.

## Source-image safety policy

SRK's reusable readers open source media read-only. APIs that create outputs reject known source-image/CUE/track collisions. Extraction writes only beneath a caller-provided destination and validates output path components before writing.

The project policy is simple:

> Original source media is never modified in place.

Future patch/rebuild tooling must create a separate output image and preserve this invariant in automated tests.

## Architecture

```text
rikai_kotoba/
├── cli.py
├── core/
│   ├── disc_source.py
│   ├── disc_image.py
│   ├── cue_disc.py
│   ├── iso9660.py
│   ├── safe_extractor.py
│   └── hex_dump.py
├── formats/
│   └── saturn/
│       └── ip_bin.py
├── tools/
│   └── mjolnir.py
└── hardware/
    └── saturn/
        └── saroo/
```

The `hardware/saturn/saroo/` namespace is reserved for upcoming original-hardware development/debug tooling. Hardware tooling is intended to remain generic; title-specific addresses and experimental research do not belong in the reusable core.

## Testing

The committed test suite uses synthetic fixtures and temporary files; it does not require copyrighted game data.

Run the standard-library test suite:

```bash
python -m unittest discover -s tests -v
```

Or, with development extras installed:

```bash
pytest
```

## Current CUE limitations

The CUE layer currently focuses on the layouts needed for safe generic data access. Known limitations include:

- `PREGAP` directives are not yet modeled separately;
- tracks sharing one physical file but using different physical sector sizes are rejected;
- AUDIO tracks are represented in logical disc space but intentionally do not expose a 2048-byte ISO user-data payload.

Unsupported layouts should fail explicitly rather than be guessed.

## Legal / data policy

SRK does not include commercial game images, extracted copyrighted game assets, or proprietary SDK material. Use the toolkit only with software and media you are legally permitted to inspect or modify.

## License

MIT. See `LICENSE`.
