# SAROO Capture and Provenance

SRK uses SAROO as an original-hardware research laboratory for Sega Saturn. The
public framework remains title-neutral: addresses, ranges, checkpoints, and
captures are explicit inputs rather than hardcoded knowledge about one game.

## Goal

The evidence chain SRK is trying to establish is:

```text
disc
  -> file / LBA / file offset
  -> loader / decode / decompress / relocate
  -> Saturn RAM
  -> execution / display
```

Static analysis can identify plausible data. Runtime capture tells us whether the
console actually loaded or transformed that data.

## Current layers

```text
Saturn / SAROO
      |
      v
transport adapter
      |
      v
SarooCaptureCoordinator
      |
      v
CapturedRegion + CaptureStore
      |
      +--> capture.json + SHA-256 region files
      |
      v
exact correlation / future transformed-data analyzers
```

The storage and analysis layers do not depend on one transport mechanism.

## Verified upstream SAROO primitive

SRK's initial Saturn-side helper was researched against upstream SAROO commit:

```text
c31bf6192eff59533d7268dfdf6c791f11a1f7c9
```

Relevant upstream behavior:

- `Firm_Saturn/main.h` declares `write_file(name, offset, size, buf)`;
- `Firm_Saturn/main.c` routes that operation through `SSCMD_FILEWR`;
- the MCU-side handler uses `offset == -1` for create/truncate and explicit
  non-negative offsets for later writes;
- upstream `Firm_Saturn/sci_shell.c` includes an `fwt` diagnostic that sends
  `0x10000` bytes from Saturn memory through `write_file()`.

SRK therefore treats **64 KiB** as the currently verified staging-write size.
The public helper does not assume that a full 1 MiB Work RAM region is safe in a
single staging-buffer operation.

## Chunked Work RAM capture

Canonical title-neutral Saturn regions currently modeled by SRK:

```text
Work RAM-L  0x00200000 - 0x002FFFFF  1 MiB
Work RAM-H  0x06000000 - 0x060FFFFF  1 MiB
```

A 1 MiB region is written as sixteen 64 KiB chunks. The first call uses upstream
`offset == -1` create/truncate semantics; later calls use explicit file offsets.

SRK-authored integration source lives under:

```text
integrations/saroo/Firm_Saturn/
```

The helper deliberately does **not** decide how capture is triggered. Shell
commands, breakpoint/debug hooks, controller hotkeys, and future live transports
are separate policy/mechanism layers.

## Raw SD-file import

A raw file copied from SAROO's SD card can be normalized into SRK's verified
capture format:

```bat
srk import-saroo-dump SRK_WRAMH.BIN ^
    --base-address 0x06000000 ^
    --expected-size 0x100000 ^
    --checkpoint title-screen ^
    --label work_ram_high
```

Unless overridden with `--capture-root`, SRK writes the resulting immutable
artifact beneath:

```text
SRK-Workspace/Dumps/SAROO/
```

The original raw file is never modified.

Each published capture contains:

```text
<timestamp>_<checkpoint>/
├── 00_<label>_<address>_<size>.bin
└── capture.json
```

The JSON manifest records:

- capture schema/version;
- platform and transport family;
- checkpoint and optional session label;
- UTC capture/import timestamp;
- region start/end addresses and sizes;
- per-region SHA-256 hashes.

`verify_capture()` detects missing, resized, or modified region data.

## Exact correlation

The first correlation engine intentionally makes only conservative claims:

```bat
srk correlate SOURCE_FILE CAPTURE_REGION.bin --base-address 0x06000000
```

It:

- streams source chunks;
- searches exact byte sequences in the RAM dump;
- suppresses chunks that occur too many times to be useful evidence;
- coalesces adjacent exact matches with one consistent source-to-memory
  displacement;
- hashes both inputs.

It does **not** yet claim to recognize decompression, pointer fixups, decoding,
byte swapping, or relocation transformations. Those require dedicated analyzers
and additional evidence.

## Live transport policy

The current desktop installs `UnconfiguredSarooTransport`. This is intentional.
Capture buttons remain disabled until a concrete adapter can prove it is
available.

The public contract is:

```text
status()
read_memory(MemoryRange)
close()
```

When a verified live adapter exists, it can replace the unconfigured transport
without changing capture persistence, controller threading, GUI event delivery,
or provenance analysis.

## Thread ownership

Potentially blocking hardware activity always crosses the existing SRK worker
boundary:

```text
Dear PyGui action
      |
      v
SarooCaptureController
      |
      v
BackgroundWorkerService
      |
      +---- worker thread ----> SarooCaptureCoordinator / transport
      |                              |
      |                         immutable event/result
      |                              |
      +-------- thread-safe queue <--+
                     |
                     v
Salix ApplicationRuntime.update()
          on application thread
                     |
                     v
Dear PyGui presentation
```

A transport implementation must never update Dear PyGui directly.

## Public/private boundary

The reusable repository may contain:

- Saturn hardware-region definitions;
- generic capture helpers;
- transport interfaces;
- manifests/hashing;
- correlation algorithms;
- synthetic tests.

It must not contain:

- commercial-game images or extracted assets;
- title-specific runtime addresses/signatures;
- private experimental patches;
- per-game hook constants.

Those belong in private research/project profiles outside the reusable core.
