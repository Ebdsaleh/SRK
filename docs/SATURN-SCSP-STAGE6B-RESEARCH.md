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

## Read-only evidence probe

SRK now provides:

```text
python -m rikai_kotoba.tools.saturn_cd_runtime_probe --saturn-root <Saturn-Dev>
```

The probe:

- recursively inspects the supplied Saturn development root read-only;
- reports GFS/CDC-named static libraries;
- reports likely CD/GFS/CDC headers;
- scans bounded text/source/example material for `GFS_*`, `sega_gfs`, and `libgfs` evidence;
- prints file/line locations and short matching lines for review;
- never copies, modifies, links, executes, or writes any local Saturn file.

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
