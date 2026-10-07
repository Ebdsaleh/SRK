# SAROO `Firm_Saturn` Toolchain Preflight

SRK prepares and researches a title-neutral Saturn-side memory-capture helper for
upstream SAROO. Before attempting a firmware build, SRK can perform a **read-only
preflight** for the external build programs still required by the separate
SRK-generated `Firm_Saturn` tree.

This document describes discovery only. Nothing here flashes SAROO hardware or
modifies a known-good SAROO checkout.

## Upstream and generated build contracts

The pinned upstream `Firm_Saturn/Makefile` uses these SH-ELF programs:

```text
sh-elf-gcc
sh-elf-as
sh-elf-objdump
sh-elf-objcopy
```

It also invokes a Make-compatible build driver and historically uses the
Unix-style file commands `touch`, `cat`, and `rm`.

Physical inspection of SaturnOrbit R1 showed that its SH-ELF payload provides
all four SH-ELF programs and `make.exe`, but does **not** provide `touch.exe` or
`cat.exe`. Rather than add unrelated utility packages, SRK rewrites those three
small file-operation recipes only in the **separate generated build tree** and
supplies `srk_build_support.py`, which implements the equivalent operations with
Python's standard library.

Therefore the external programs required by an SRK-generated build are:

```text
sh-elf-gcc
sh-elf-as
sh-elf-objdump
sh-elf-objcopy
make
```

SRK recognizes `make`, `gmake`, or `mingw32-make` as possible Make-compatible
drivers and records the exact executable that was resolved.

Upstream SAROO's README states that `Firm_Saturn` is built with the SH-ELF
compiler distributed with SaturnOrbit.

The SRK integration was researched against upstream SAROO commit:

```text
c31bf6192eff59533d7268dfdf6c791f11a1f7c9
```

## Verified SaturnOrbit R1 layout

The user's SaturnOrbit R1 package was inspected without executing its legacy
installer. The extracted payload contained:

```text
SaturnOrbit\
└── SH_ELF\
    ├── sh-elf\bin\
    │   ├── sh-elf-gcc.exe
    │   ├── sh-elf-as.exe
    │   ├── sh-elf-objdump.exe
    │   └── sh-elf-objcopy.exe
    └── Other Utilities\
        ├── make.exe
        └── rm.exe
```

The inspected R1 payload did not contain `touch.exe`, `cat.exe`, or
`mingw32-make.exe`. SRK does not require those missing executables for its
generated build because the generated Makefile uses the bundled Python helper
for `touch`, concatenation, and removal.

The explicit-root search still understands several common nested toolchain
layouts and performs a bounded recursive search, so another compatible SH-ELF
distribution does not need to reproduce this exact directory tree.

## Do not use upstream `MAKE_ELF.bat` as the SRK build entry point

The pinned upstream SAROO tree also contains `Firm_Saturn/MAKE_ELF.bat`, but that
historical helper contains machine-specific absolute paths such as
`F:\SaturnOrbit\SET_ELF.BAT` and another unrelated `F:` output destination.

SRK therefore does **not** treat that batch file as the portable build contract.
The intended build path is:

```text
separate generated Firm_Saturn tree
+
explicit process-local toolchain environment
+
generated portable Makefile recipes
```

The known-good upstream checkout, the user's global `PATH`, and the extracted
SaturnOrbit source package remain untouched by source preparation.

## Run the preflight

After installing the current SRK editable package:

```bat
srk-saroo-toolchain
```

With no argument, SRK inspects the existing process `PATH` without changing it.

If the required tools are bundled somewhere beneath a SaturnOrbit or toolchain
directory, point SRK at the containing root:

```bat
srk-saroo-toolchain --toolchain-root "C:\path\to\SaturnOrbit"
```

The explicit root is searched first. SRK understands common nested `bin`,
`sh-elf/bin`, `toolchain/bin`, and historical SaturnOrbit directories, then
performs a bounded recursive search beneath the directory.

Example successful report:

```text
SAROO Firm_Saturn toolchain preflight
--------------------------------------------
Explicit root : C:\SaturnOrbit
PATH policy   : read-only fallback; PATH is not modified

[OK]      sh-elf-gcc       C:\SaturnOrbit\...\sh-elf-gcc.exe (toolchain-root)
[OK]      sh-elf-as        C:\SaturnOrbit\...\sh-elf-as.exe (toolchain-root)
[OK]      sh-elf-objdump   C:\SaturnOrbit\...\sh-elf-objdump.exe (toolchain-root)
[OK]      sh-elf-objcopy   C:\SaturnOrbit\...\sh-elf-objcopy.exe (toolchain-root)
[OK]      make             C:\SaturnOrbit\...\make.exe (toolchain-root)

Discovery result: READY - every required executable was resolved.
```

## What `READY` means

`READY` means only that every external executable required by the generated
build could be resolved.

It does **not** yet prove that:

- the compiler binaries execute correctly on this Windows installation;
- headers/libraries expected by the Makefile are complete;
- the generated SRK-enabled `Firm_Saturn` tree compiles or links;
- the resulting firmware is correct for the user's SAROO hardware;
- any firmware has been installed or flashed.

The next evidence step after a successful preflight is a real build of a
**separate generated source tree**.

## Safety policy

The preflight:

- does not modify the process or global `PATH`;
- does not write into the supplied toolchain directory;
- does not modify a SAROO checkout;
- does not invoke a compiler;
- does not build firmware;
- does not copy files to an SD card;
- does not flash hardware.

If an explicit `--toolchain-root` does not exist, SRK reports an error rather than
silently searching an unrelated location.

## Related commands

Prepare a separate SRK-enabled copy of upstream `Firm_Saturn` source:

```bat
srk prepare-saroo-firmware C:\path\to\SAROO C:\path\to\SAROO-SRK
```

Import a raw Work RAM file copied from the SAROO SD card:

```bat
srk import-saroo-dump SRK_WRAMH.BIN ^
    --base-address 0x06000000 ^
    --expected-size 0x100000 ^
    --checkpoint title-screen ^
    --label work_ram_high
```

The source SAROO checkout and original raw dump remain untouched by these
workflows.
