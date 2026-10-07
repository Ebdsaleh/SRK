# SRK — Salix Rikai Kotoba

SRK is a modular retro-disc localization and reverse-engineering toolkit written in Python. The project begins with Sega Saturn support while keeping reusable disc, ISO-9660, extraction, hexadecimal, application, and Salix RAD layers platform- and game-agnostic.

SRK is currently alpha software. The public repository intentionally contains no game-specific offsets, patches, extracted commercial game data, or disc images.

## Core goals

- Treat original disc images as **read-only sources**.
- Model CUE-backed multi-track discs as one logical LBA space.
- Read ISO-9660 files without loading complete disc images into memory.
- Surface unsupported/non-data extents explicitly instead of silently creating partial or zero-byte output.
- Keep platform-specific format knowledge separate from generic disc infrastructure.
- Keep title-specific research outside the reusable public core.
- Build the desktop as an SRK application **on the Salix RAD framework**, rather than maintaining an SRK-specific GUI framework.
- Keep Dear PyGui on the presentation/owner thread and route background results through explicit worker events supervised by the Salix runtime.
- Ship a detailed offline Help/Glossary so the application remains usable and educational without Internet access.
- Build Saturn runtime research around reproducible captures and provenance evidence rather than title-specific guesswork.

## Current capabilities

### Generic disc layer

- Standalone `BIN`, `IMG`, `ISO`, and `RAW` image access.
- Automatic detection of supported 2048-byte and 2352-byte data-sector layouts.
- CUE parsing with multi-file logical-LBA mapping.
- Explicit AUDIO-track detection.
- ISO-9660 directory walking, path lookup, and file reads.
- Safe extraction with traversal protection and source-collision checks.
- Standard hex rendering and file output.
- Exact source-file-to-memory correlation for runtime provenance research.

### Sega Saturn

- Saturn `IP.BIN` boot-header inspection from logical LBA 0.
- Canonical 1 MiB Work RAM-L (`0x00200000`) and Work RAM-H (`0x06000000`) capture regions.
- Title-neutral SAROO memory-range capture contracts.
- Atomic SAROO capture artifacts containing raw region files plus SHA-256 `capture.json` metadata.
- Capture verification that detects size/hash changes after a dump is recorded.
- Saturn-specific code lives under `rikai_kotoba.formats.saturn` and `rikai_kotoba.hardware.saturn` rather than in the generic core.

The real SAROO communication adapter is intentionally **not guessed**. The desktop exposes the capture pipeline and keeps capture buttons disabled until a verified transport implementation reports itself available.

### Salix RAD desktop foundation

SRK's GUI is a product application built on the reusable Salix architecture extracted from the Salix application family. The public tree separates:

- `salix.runtime` — backend-neutral application metadata, lifecycle supervision, presentation capabilities, scenes, diagnostics, and path policy;
- `salix.framework` — property cascade, geometry, responsive coordination, semantic components, interactions, command menus, and documentation contracts;
- `salix.engine` — concrete Dear PyGui application hosts, renderers, layout/scene/menu adapters, typography, and documentation rendering;
- `rikai_kotoba` — SRK's disc, Saturn, SAROO, localization/research workflows, application services, and product views.

SRK deliberately does **not** maintain a parallel `rikai_kotoba.runtime` or `rikai_kotoba.engine` framework.

The desktop currently provides:

- **Disc Workspace** — open and index a CUE or standalone disc without running the scan on the UI thread;
- **Saturn / SAROO** — title-neutral transport status, canonical Work RAM capture controls, checkpoint/session metadata, and external capture destination;
- **Diagnostics** — Salix runtime state, SRK worker-pool state, queue depth, and UI error-log location;
- **Offline Help & Glossary** — searchable novice-oriented documentation with Contents navigation, A-Z glossary navigation, scalable documentation text, and cross-linked semantic pages.

Only the Dear PyGui owner thread may touch Dear PyGui widgets. SRK background workers publish immutable events through a thread-safe queue; the worker service is updated by Salix `ApplicationRuntime` on the application thread before product views consume those events.

See [`docs/DESKTOP-ARCHITECTURE.md`](docs/DESKTOP-ARCHITECTURE.md).

### Mjölnir

Mjölnir is SRK's interactive disc/hex research utility. It can:

- discover CUE sheets and standalone images;
- prefer a CUE over the physical track files it references;
- list the reachable ISO-9660 filesystem;
- select and dump individual files as hex;
- create one complete filesystem hex blob;
- create structured filesystem extractions;
- create portable ZIP dumps;
- resolve output conflicts with **Cancel / Auto-rename / Overwrite** behavior.

Mjölnir accepts an image file or a directory supplied by the user. It does not assume a repository-local game directory.

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

The package installs three console commands:

```text
srk
srk-gui
srk-mjolnir
```

You can also run the CLI package directly:

```bash
python -m rikai_kotoba
```

## Desktop examples

Launch the desktop shell:

```bash
srk-gui
```

A normal desktop launch defaults generated artifacts to:

```text
~/SRK-Workspace/Output
```

and SAROO captures to:

```text
~/SRK-Workspace/Dumps/SAROO
```

Set `SRK_WORKSPACE_DIR` to override the workspace root, or pass `--output-dir` for one launch:

```bash
srk-gui /path/to/disc.cue --output-dir /path/to/SRK-Workspace/Output
```

The GUI never requires images to live inside the Git repository. Use the Disc Workspace file chooser to select media from any location.

The Help scene is designed to function offline. It explains the application workflow and terms such as CUE, BIN, track, sector, LBA, ISO-9660, `IP.BIN`, SAROO, RAM dumps, correlation, and provenance without assuming that the reader already knows optical-disc or reverse-engineering terminology.

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

Search a raw Saturn RAM capture for exact chunks from an extracted disc file:

```bash
srk correlate /path/to/FILE.BIN /path/to/ram.bin --base-address 0x06000000
```

The correlator streams the source file, hashes both inputs, suppresses highly repeated ambiguous chunks, and coalesces adjacent exact matches into longer provenance runs. An exact run proves that those bytes occur in the capture; it does **not** claim to detect decompression, relocation fixups, decoding, byte swapping, or other transformations.

## Mjölnir examples

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

## Suggested workspace separation

The default non-portable workspace follows this layout:

```text
SRK-Workspace/
├── Images/
│   └── Saturn/
├── Output/
└── Dumps/
    └── SAROO/
```

This keeps original media, generated analysis, hardware captures, and public source code clearly separated.

## SAROO capture artifacts

A successful capture is published as a new timestamped directory under `Dumps/SAROO`. Existing capture directories are never overwritten. Each capture contains one binary file per requested address range plus `capture.json` metadata recording:

- checkpoint and optional session labels;
- capture time in UTC;
- start/end address and byte size for every region;
- SHA-256 for every region file;
- a versioned SRK capture schema.

Capture files are first written to a temporary sibling directory and are published only after every region and the manifest succeed. `verify_capture()` can later confirm size and SHA-256 integrity.

The transport boundary is deliberately small: a concrete adapter reports status, reads an explicit `MemoryRange`, and closes. Capture persistence, worker-thread orchestration, GUI state, and correlation are therefore independent of how a verified SAROO firmware ultimately moves bytes off the Saturn.

## Source-image safety policy

SRK's reusable readers open source media read-only. APIs that create outputs reject known source-image/CUE/track collisions. Extraction writes only beneath a caller-provided destination and validates output path components before writing.

The project policy is simple:

> Original source media is never modified in place.

Future patch/rebuild tooling must create a separate output image and preserve this invariant in automated tests.

## Architecture

```text
src/
├── salix/
│   ├── runtime/
│   ├── framework/
│   │   ├── components/
│   │   └── documentation/
│   └── engine/
│       ├── application_hosts/
│       ├── component_renderers/
│       ├── layout_hosts/
│       ├── scene_hosts/
│       ├── command_menu_hosts/
│       ├── presentation_backends/
│       └── documentation/
│
└── rikai_kotoba/
    ├── cli.py
    ├── desktop.py
    ├── core/
    │   ├── correlation.py
    │   ├── disc_source.py
    │   ├── disc_image.py
    │   ├── cue_disc.py
    │   ├── iso9660.py
    │   ├── safe_extractor.py
    │   └── hex_dump.py
    ├── application/
    │   ├── controller.py
    │   ├── disc_workspace.py
    │   ├── saroo_capture.py
    │   ├── workers.py
    │   ├── paths.py
    │   └── help_content.py
    ├── views/
    │   ├── main_viewport.py
    │   ├── disc_workspace.py
    │   ├── saroo.py
    │   ├── diagnostics.py
    │   └── help.py
    ├── formats/
    │   └── saturn/
    │       └── ip_bin.py
    ├── tools/
    │   └── mjolnir.py
    └── hardware/
        └── saturn/
            ├── memory_map.py
            └── saroo/
                ├── capture.py
                └── transport.py
```

The dependency direction is deliberate. SRK core/application code does not import Dear PyGui; Salix framework/runtime code does not import Dear PyGui or SRK product code; concrete toolkit adapters live under `salix.engine`.

## Thread model

```text
Dear PyGui action
      |
      v
SRK controller
      |
      v
SRK BackgroundWorkerService
      |
      +---- worker thread ----> core/application/hardware work
      |                              |
      |                         WorkerEvent
      |                              |
      +-------- thread-safe queue <--+
                     |
                     v
Salix ApplicationRuntime.update()
          on application thread
                     |
                     v
controller/view subscribers
                     |
                     v
Dear PyGui presentation
```

The worker pool belongs to the SRK product because its jobs are product-specific; lifecycle supervision belongs to Salix.

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

Architecture tests guard the Salix-first boundary: backend-neutral SRK layers cannot import Dear PyGui, Salix framework/runtime cannot depend on SRK or Dear PyGui, and SRK cannot reintroduce parallel runtime/engine packages.

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
