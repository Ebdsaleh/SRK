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
- `hardware/saturn/saroo/` is reserved for generic original-hardware capture/debug tooling.

### Salix RAD desktop foundation

SRK's GUI is a product application built on the reusable Salix architecture extracted from the Salix application family. The public tree separates:

- `salix.runtime` — backend-neutral application metadata, lifecycle supervision, presentation capabilities, scenes, diagnostics, and path policy;
- `salix.framework` — property cascade, geometry, responsive coordination, semantic components, interactions, command menus, and documentation contracts;
- `salix.engine` — concrete Dear PyGui application hosts, renderers, layout/scene/menu adapters, typography, and documentation rendering;
- `rikai_kotoba` — SRK's disc, Saturn, SAROO, localization/research workflows, application services, and product views.

SRK deliberately does **not** maintain a parallel `rikai_kotoba.runtime` or `rikai_kotoba.engine` framework.

The desktop currently provides:

- **Disc Workspace** — open and index a CUE or standalone disc without running the scan on the UI thread;
- **Saturn / SAROO** — presentation shell for the upcoming flight-recorder/capture toolchain;
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

Open one disc after startup and choose a separate output workspace:

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

Keep media and generated research outside the source-code repository, for example:

```text
SRK-Workspace/
├── Images/
│   └── Saturn/
├── Output/
└── Dumps/
    └── SAROO/
```

This keeps original media, generated analysis, hardware captures, and public source code clearly separated.

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
    │   ├── disc_source.py
    │   ├── disc_image.py
    │   ├── cue_disc.py
    │   ├── iso9660.py
    │   ├── safe_extractor.py
    │   └── hex_dump.py
    ├── application/
    │   ├── controller.py
    │   ├── disc_workspace.py
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
            └── saroo/
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
