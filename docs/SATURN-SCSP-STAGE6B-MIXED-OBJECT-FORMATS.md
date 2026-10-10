# Saturn SCSP Stage 6B — mixed ELF/COFF and SBL dependency closure

## Status

Stage 6B Gate 2 reached the final link after every SRK C source compiled and the
startup source assembled successfully. The link stopped on the installed
`SEGA_CDC.A` with:

```text
could not read symbols: File format is ambiguous
```

Gate 3 explicitly scoped CDC as `coff-sh`; that removed the format ambiguity
and exposed the next layer of normal static-library dependencies. No ISO or
SAROO/card write occurred in either failed gate.

## Mjolnir format evidence

Mjolnir established that the reviewed SBL libraries use normal classic Unix
`ar` containers, but their member object formats differ.

### `sega_gfs.a`

- classic Unix `ar`;
- 7 payload members;
- ELF32, big-endian, relocatable, machine SH (42).

### `SEGA_CDC.A`

- classic Unix `ar`;
- 17 payload members;
- Hitachi SH big-endian COFF (`0x0500`).

### `SEGADGFS.A`

- classic Unix `ar`;
- 12 payload members;
- Hitachi SH COFF as well;
- useful format evidence, but not required by the selected dedicated GFS link
  path.

The archive wrapper itself is healthy. It does not need repacking.

## Gate 3 dependency evidence

With the CDC input format disambiguated, the real linker exposed GFS's missing
support symbols in one batch:

```text
_memcmp
_strncmp
_memset
_strncpy
_DMA_ScuSetPrm
_DMA_ScuStart
_CSH_Purge
_DMA_ScuGetStatus
_DMA_CpuStop
_DMA_CpuSetComPrm
_DMA_CpuSetPrm
_DMA_CpuStart
_DMA_CpuGetStatus
```

Rather than add libraries one failure at a time, Mjolnir was expanded into a
Saturn-first object/archive workbench and run across the entire installed
`LIB_ELF` tree.

The SDK-wide pass decoded 336 objects and built a cross-format symbol provider /
consumer graph. For the selected GFS path it proved these direct edges:

```text
sega_gfs.a -> SEGA_CDC.A   (35 CDC symbols)
sega_gfs.a -> sega_dma.a   (8 DMA symbols)
sega_gfs.a -> sega_csh.a   (_CSH_Purge)
```

It also proved the dedicated DMA transitive edges:

```text
sega_dma.a -> sega_csh.a   (_CSH_Purge)
sega_dma.a -> sega_int.a   (_INT_GetScuFunc, _INT_SetScuFunc)
```

The broad `sega_sat.a` aggregate exports duplicate providers, but Stage 6B does
not need that large umbrella library. `SEGADGFS.A` also contains duplicate GFS
providers but is not part of the selected ELF GFS path.

## Freestanding C runtime surface

The SDK-wide index found no SBL `LIB_ELF` providers for these ordinary C ABI
symbols consumed by `sega_gfs.a`:

```text
_memcmp
_memset
_strncmp
_strncpy
```

The standalone image intentionally remains `-nostdlib`. SRK therefore provides
a tiny deterministic freestanding implementation of those functions in
`srk_saturn_runtime.c`. The already accepted startup assembly continues to
provide `_memcpy` for compiler/SBL aggregate-copy calls.

Compiler helper symbols used by GFS, such as division/shift helpers, remain the
responsibility of the existing final `-lgcc` link.

## Complete Stage 6B dedicated link contract

The production Python-native builder and bounded probe now share one explicit
link order:

```text
... SRK ELF objects, including srk_saturn_runtime.o ...
sega_gfs.a
--format=coff-sh
SEGA_CDC.A
--format=elf32-sh
sega_dma.a
sega_csh.a
sega_int.a
-lgcc
```

Ordering matters:

1. GFS appears before the libraries that satisfy its unresolved symbols.
2. Only `SEGA_CDC.A` is interpreted as `coff-sh`.
3. The linker is reset to `elf32-sh` immediately after CDC.
4. DMA precedes its cache/interrupt providers.
5. `libgcc` remains last for compiler-emitted helpers.

Every private SBL artifact is pinned by path, size, and SHA-256 in the generated
project manifest and remains outside the generated project tree.

## Mjolnir architectural rule

Mjolnir is part of SRK's general Saturn reverse-engineering layer. New Saturn
containers, object formats, symbol conventions, and dependency structures must
be taught to Mjolnir generically rather than implemented as disposable
single-file probes. Current binary mode supports Unix `ar`, ELF, Hitachi SH
COFF, normalized object sections/symbols, recursive SDK scanning, symbol search,
and cross-library dependency resolution without invoking `nm`, `objdump`, `ar`,
or the linker.

## Next gate

After the source test gate passes, prepare a **fresh** Stage 6B project and run
the normal Python-native builder. The next acceptance gate is a complete
off-card build: compile, mixed-format link, ISO construction, packaged PCM
verification, MODE1/2352 BIN/CUE generation, and post-build private dependency
verification.

No SAROO/card write is authorized by this gate. Physical R17 remains blocked
until the full build succeeds and the remaining Sega GFS API return/size
semantics are grounded from exact documentation/examples.
