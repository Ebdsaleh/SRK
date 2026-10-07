# SAROO `Firm_Saturn` Toolchain and Native Build

SRK prepares and researches a title-neutral Saturn-side memory-capture helper for
upstream SAROO. The source-preparation and build workflows operate only on a
**separate generated `Firm_Saturn` tree**; the known-good upstream SAROO checkout
is never edited in place.

Nothing in this workflow automatically copies firmware to an SD card or flashes
SAROO hardware.

## External tools actually required

The generated `Firm_Saturn/Makefile` describes the SH-ELF compiler flags, object
order, linker flags, and libraries used by upstream SAROO. SRK reads that build
contract, but it does **not** execute GNU Make.

The only external programs required by SRK's controlled build are:

```text
sh-elf-gcc
sh-elf-as
sh-elf-objdump
sh-elf-objcopy
```

Python performs the orchestration directly:

```text
SRK Python build driver
        |
        +--> clean previous generated outputs
        +--> sh-elf-as / sh-elf-gcc for every object
        +--> sh-elf-gcc link
        +--> sh-elf-objdump -> dump.txt
        +--> sh-elf-objcopy -> temporary binary
        +--> Python concatenation -> ssfirm.bin
        +--> SHA-256 artifact verification
```

GNU Make, MSYS `sh.exe`, CMake, Ninja, `touch`, `cat`, and `rm` are not required
by this controlled path.

The SRK integration was researched against upstream SAROO commit:

```text
c31bf6192eff59533d7268dfdf6c791f11a1f7c9
```

## Verified SaturnOrbit R1 layout

Physical inspection of SaturnOrbit R1 found the required SH-ELF programs beneath:

```text
SaturnOrbit\
└── SH_ELF\
    └── sh-elf\bin\
        ├── sh-elf-gcc.exe
        ├── sh-elf-as.exe
        ├── sh-elf-objdump.exe
        └── sh-elf-objcopy.exe
```

SaturnOrbit also contains historical Make/MSYS utilities, but SRK deliberately
does not depend on them. This avoids legacy shell/parser behavior on modern
Windows while retaining SaturnOrbit's actual SuperH compiler and object tools.

The explicit-root search understands common nested toolchain layouts and
performs a bounded recursive search, so another compatible SH-ELF distribution
does not need to reproduce this exact directory tree.

## Toolchain preflight

Run the read-only preflight with:

```bat
srk-saroo-toolchain --toolchain-root "C:\path\to\SaturnOrbit"
```

A successful report resolves the four SH-ELF programs. The command does not
modify the process/global `PATH`, invoke the compiler, write into the toolchain,
or touch an SD card.

`READY` means discovery succeeded. A real build is still the authoritative proof
that the compiler installation works.

## Controlled native build

Prepare a separate SRK-enabled source tree once:

```bat
srk prepare-saroo-firmware C:\path\to\SAROO C:\path\to\SAROO-SRK
```

Then build it with:

```bat
srk build-saroo-firmware ^
  "C:\path\to\SAROO-SRK" ^
  --toolchain-root "C:\path\to\SaturnOrbit"
```

The native builder streams progress to the console and simultaneously writes a
unique `SRK_BUILD_LOG*.txt` beside the generated tree. Each SH-ELF command and
its output are retained in the log.

Expected build artifacts are:

```text
Firm_Saturn/ssfirm.elf
Firm_Saturn/ssfirm.bin
Firm_Saturn/dump.txt
```

A successful result requires clean/build exit `0` and all three artifacts. SRK
records their sizes and SHA-256 hashes.

## Physical validation — 2026-10-07

The Python-native driver at SRK commit:

```text
7e4703da1c1501b57902130ac6066bf3b87a873b
```

was physically validated on Windows with Python 3.13.3 and the installed
SaturnOrbit R1 SH-ELF toolchain.

Repository validation before the physical build:

```text
unittest: 190 passed
pytest:   190 passed, 23 subtests passed
```

The real generated `Firm_Saturn` build compiled all 17 objects, linked, and
published the expected outputs with clean/build exit `0`:

```text
ssfirm.elf   89,518 bytes
SHA-256 fd9adc19c4991c51bae3e8cc65e5f94161b8ee7a411db5e459748b99a2bc2837

ssfirm.bin  484,246 bytes
SHA-256 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686

dump.txt    837,322 bytes
SHA-256 e102d97ca8dfd29d9e206ee4537f71ce1d552a313a9b86e24a5b6d367a7eaf40
```

No firmware was copied to SD and no hardware was flashed during this validation.

## Inspect the real SD card before any deployment

SAROO has used more than one Saturn-firmware filename/location across its
history. SRK therefore does not infer an installation path from the build output
alone.

Use the read-only inspector on the mounted SD-card root first:

```bat
srk inspect-saroo-sd E:\
```

It recognizes:

```text
modern layout: SAROO/ssfirm.bin
legacy layout: ramimage.bin at the SD-card root
```

It hashes any recognized existing Saturn firmware and reports companion layout
evidence (`mcuapp.bin`, `saroocfg.txt`, `ISO`, `update`). If both known firmware
locations are present, SRK reports a mixed/ambiguous layout instead of guessing.

The inspector never writes to the card. A later staging/deployment workflow must
use this evidence before proposing a replacement path.

## Safety policy

The controlled SAROO workflow currently guarantees that:

- the original SAROO source checkout is not edited in place;
- the original commercial game image is unrelated to and untouched by firmware
  preparation/build operations;
- tool discovery does not modify global/process `PATH`;
- the build driver does not execute historical Make/MSYS shell tooling;
- numbered build logs and artifact hashes preserve build evidence;
- SD-card layout inspection is read-only;
- firmware is never copied to SD or flashed implicitly.

## Related commands

Import a raw Work RAM file copied from the SAROO SD card:

```bat
srk import-saroo-dump SRK_WRAMH.BIN ^
    --base-address 0x06000000 ^
    --expected-size 0x100000 ^
    --checkpoint title-screen ^
    --label work_ram_high
```

The original raw dump remains untouched; SRK publishes a new verified capture
artifact with SHA-256 metadata.
