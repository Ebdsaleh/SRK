# Mjolnir binary/object/archive workbench

Mjolnir is SRK's general reverse-engineering workbench. The Sega Saturn is SRK's
first platform, so Saturn file and binary research is a first-class Mjolnir
responsibility rather than a collection of one-off diagnostic scripts.

The existing disc side understands CUE/BIN geometry, ISO-9660 filesystems,
read-only file extraction, and hex research. The binary side now applies the same
principles to development libraries and object files.

## Design rule

When Saturn research exposes a new reusable file/container/object structure, it
belongs in a general Mjolnir/core decoder with tests and a common inspection
surface. Project-specific investigations may consume those decoders, but they
must not become the only place where the format knowledge exists.

That keeps Mjolnir a real Swiss-army-knife rather than a sequence of narrowly
hard-coded fixes.

## Current binary capabilities

Mjolnir currently understands, without external binutils:

- classic Unix `ar` archives;
- standard/GNU/BSD archive member naming;
- archive member offsets, exact sizes, SHA-256, and raw signatures;
- ELF32 and ELF64 in either byte order;
- ELF section tables and symbol tables;
- Hitachi SuperH COFF (`0x0500` big-endian / `0x0550` little-endian);
- SH COFF section tables, string tables, symbols, and auxiliary-record skipping;
- a normalized ELF/COFF object model;
- global/weak symbol definitions and undefined references;
- recursive directory scans of common object/archive file extensions;
- cross-object and cross-library symbol provider/consumer indexes;
- resolved source-library dependency edges;
- unresolved external-symbol reports;
- exact or substring symbol searches across mixed ELF/COFF inputs.

This means Mjolnir can inspect a Saturn SDK library directory as a coherent
binary ecosystem rather than examining one archive at a time.

## Safety contract

Inspection is read-only:

- source files are never modified;
- archive members are parsed in place and are not extracted;
- no compiler, linker, `ar`, `nm`, `objdump`, or BFD process is required;
- no SDK library is copied into SRK;
- directory scans create no output tree;
- malformed structures fail closed with bounded reads;
- unknown formats stay unknown rather than being guessed.

## Entry points

Installed console entry point:

```bat
srk-mjolnir-binary "C:\path\to\library.a"
```

Module form:

```bat
python -m rikai_kotoba.tools.mjolnir_binary "C:\path\to\library.a"
```

Multiple files can be compared directly:

```bat
python -m rikai_kotoba.tools.mjolnir_binary ^
  "C:\path\to\one.a" ^
  "C:\path\to\two.a"
```

A complete library directory can be scanned recursively:

```bat
python -m rikai_kotoba.tools.mjolnir_binary ^
  "C:\path\to\LIB_ELF" ^
  --recursive --all
```

Useful focused forms:

```bat
rem Show external symbols from every decoded object.
python -m rikai_kotoba.tools.mjolnir_binary "C:\path\to\LIB_ELF" --recursive --symbols

rem Resolve cross-library dependencies and unresolved externals.
python -m rikai_kotoba.tools.mjolnir_binary "C:\path\to\LIB_ELF" --recursive --dependencies

rem Find exact providers and consumers for one symbol.
python -m rikai_kotoba.tools.mjolnir_binary "C:\path\to\LIB_ELF" --recursive ^
  --search-symbol DMA_ScuStart --exact-symbol
```

`--member-limit` and `--symbol-limit` bound console output without changing the
underlying scan.

## Saturn-first extensibility

Mjolnir's binary path is deliberately not named after GFS, CDC, SBL, or one
specific game. New Saturn formats should extend the same pipeline:

```text
raw bytes
   -> container detection
   -> members/regions
   -> object/file decoder
   -> normalized sections/symbols/resources
   -> cross-file index/correlation
   -> hex/evidence/reporting
```

That is the architectural contract for future Saturn executable formats,
resource containers, SDK archives, game-specific containers, compression
wrappers, script/text formats, and other reverse-engineering targets.

## Stage 6B evidence already established

Mjolnir proved that:

```text
sega_gfs.a   -> Unix ar -> ELF32 big-endian SH objects
SEGA_CDC.A   -> Unix ar -> Hitachi SH big-endian COFF objects
SEGADGFS.A   -> Unix ar -> Hitachi SH big-endian COFF objects
```

The archive wrapper was never corrupt. The original linker ambiguity came from
the historical mixed ELF/COFF object boundary. The next Stage 6B step can now
use Mjolnir's general symbol/dependency index to resolve all required SBL support
libraries in one pass instead of discovering them one undefined symbol at a
time.
