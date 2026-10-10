# Saturn SCSP Diagnostic — Stage 6B CD Runtime Evidence Gate

Stage 6A proved that an SRK-owned PCM payload survives real standalone project generation, real ISO packaging, ISO read-back, and MODE1/2352 publication with exact provenance.

Stage 6B will make the Saturn itself load that packaged payload before handing it to the already accepted SCSP playback path.

The first Stage 6B step is intentionally **research-only**. SRK must identify the caller's existing Sega/SBL CD/filesystem API surface and known-good example usage before any Saturn runtime loader is written.

## Why a research gate exists

The Saturn CD block is stateful hardware with Sega-provided filesystem/runtime layers. A guessed command sequence would create unnecessary risk and would weaken attribution if a hardware test failed.

Therefore Stage 6B follows this hierarchy:

1. supplied Sega/Saturn developer documentation;
2. known-good local SBL/Saturn examples and headers;
3. installed local library/link evidence;
4. external/community material only as corroboration if needed.

No proprietary Sega source, header, static library, or documentation text is copied into public SRK.

## First real evidence pass — accepted

The first ERIDU read-only probe completed successfully at source HEAD
`6612f631025a384fd9d9e2322cd59886a7ceeb90` after the complete 389-test Python gate passed.

The local Saturn development tree supplied concrete evidence for the high-level GFS path:

- 16 GFS/CDC-named library artifacts were found;
- 31 likely CD/GFS/CDC headers were found;
- the SBL 6.01 ELF library tree contains `sega_gfs.a`, `SEGA_CDC.A`, and `SEGADGFS.A`;
- the SBL public include tree contains `SEGA_GFS.H` and `SEGA_CDC.H`;
- the Sega file-system documentation identifies `GFS_Init` as library initialization plus CD mounting;
- documented initialization uses a caller work area plus a directory-information table;
- documented root-file lookup uses `GFS_NameToId`;
- documented file operations include `GFS_Open`, `GFS_Close`, `GFS_GetFileSize`, `GFS_Fread`, and `GFS_Load`;
- a documented simple load example uses `GFS_NameToId` followed by `GFS_Load` into caller RAM;
- the documentation separately exposes non-wait/server-style functions (`GFS_Nw*`), so the first proof can deliberately avoid assuming that asynchronous path is required.

This is enough to reject a guessed low-level CD-block implementation. The supported high-level direction is clearly Sega GFS.

It is **not yet enough to write the public runtime adapter safely**, because the first broad probe did not prioritize the exact installed header declarations or the exact local build/link dependency lines. Those details remain the next research gate.

## Read-only evidence probe

SRK provides:

```text
python -m rikai_kotoba.tools.saturn_cd_runtime_probe --saturn-root <Saturn-Dev>
```

The probe:

- recursively inspects the supplied Saturn development root read-only;
- reports GFS/CDC-named static libraries;
- reports likely CD/GFS/CDC headers;
- scans bounded text/source/example material for GFS/CDC evidence;
- prints file/line locations and short matching lines for review;
- never copies, modifies, links, executes, or writes any local Saturn file.

The refined probe also prioritizes the contract details needed before runtime code:

- SHA-256 fingerprints of the preferred installed SBL GFS/CDC header/library artifacts;
- exact installed-header lines containing the target GFS API and work/directory macros;
- local makefile/config lines that name GFS/CDC link dependencies.

Use:

```text
python -m rikai_kotoba.tools.saturn_cd_runtime_probe \
  --saturn-root <Saturn-Dev> \
  --contract-only
```

The `--contract-only` form omits the large general evidence listing so the exact private dependency contract can be reviewed without copying those private files into SRK.

The output is evidence for design, not permission to reuse Sega implementation material.

## Research acceptance target

Before Stage 6B runtime code is written, the local evidence should establish enough of the supported high-level path to answer:

1. how the filesystem/CD layer is initialized;
2. how a root ISO file is identified/opened;
3. how its byte size is obtained or bounded;
4. how data is loaded into caller-provided RAM;
5. whether loading is synchronous or requires a server/poll step;
6. how handles/resources are closed or reset;
7. which include and link dependencies a known-good SH-2 build uses;
8. whether the known-good examples require additional CD subsystem initialization before GFS use.

Do not infer any of these answers from function names alone.

## Runtime scope after the research gate

The first runtime proof should remain deliberately small:

```text
ISO /SRKPCM.BIN
        |
        v
reviewed Saturn filesystem path
        |
        v
bounded WRAM buffer
        |
        v
validate SRKP v1 header
        |
        v
copy only payload samples to SRK-owned Sound RAM
        |
        v
existing accepted single-slot SCSP playback path
```

The runtime proof should reject malformed magic/version/encoding/channels/sample count/loop bounds before touching SCSP source ownership.

No streaming, WAV parsing, CDDA, DSP effects, title-resident coexistence, or arbitrary file loading belongs in the first Stage 6B hardware candidate.

## Safety

- R16 remains the last physically accepted diagnostics candidate until a later Stage 6B hardware revision passes.
- Stage 6A's off-card artifact project remains preserved.
- The read-only probe never writes the SAROO card.
- Do not copy proprietary Sega headers/libraries into the SRK repository.
- Do not implement guessed low-level CD block commands.
- A failed research/probe result stops the runtime implementation rather than triggering speculation.
