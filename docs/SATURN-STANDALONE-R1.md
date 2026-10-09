# SRK Standalone Saturn Diagnostics R1

SRK's first master-mode Saturn application is generated into a new directory and does not modify the installed Saturn SDK, reviewed examples, SAROO firmware, commercial images, or SD card.

The R1 scope is deliberately narrow:

```text
boot standalone Saturn application
render the SRK diagnostics menu
poll controller 1 directly through the Saturn manual-I/O path
show raw and normalized button state
show press / held / release state
measure simultaneous L+R hold duration at frame cadence
arm/freeze the in-RAM 30-second flight recorder
```

Not in R1:

```text
SD writes
memory dumps
SCSP/audio
VDP1 3D test
commercial-title injection
```

## Reviewed local build evidence

The reviewed `vdp1ex`/`COMMON` environment established these concrete contracts before SRK generated any project:

```text
first-read load address : 0x06004000
link output             : plain binary
stack region            : 0x06002000-0x06003FFF
controller route        : direct PDR1/DDR1/IOSEL/EXLE manual I/O
text surface            : VDP2 NBG0 8-bit bitmap + 8x8 VGA font
code-generation backend : sh-elf-gcc / sh-elf-as
ISO packaging backend   : mkisofs -generic-boot IP.BIN with cd/0.bin
```

The historical Action Replay return path, SH-COFF `stdlib.h` workaround, cartridge communication source, demo VDP1 workload, GNU Make orchestration, and shell build recipe are intentionally not inherited.

## Python-native build architecture

"Python-native build" does **not** mean Python replaces the SH-2 compiler. SRK still needs the reviewed `sh-elf-gcc`/`sh-elf-as` toolchain to translate C/assembly into SH-2 machine code, and still uses the reviewed ISO builder for disc packaging.

Python replaces the fragile orchestration layer:

```text
Python
  -> verifies generated input hashes
  -> invokes sh-elf-gcc directly for each C source
  -> invokes sh-elf-as directly for startup
  -> invokes sh-elf-gcc directly for the final link
  -> copies the first-read binary with Python file I/O
  -> invokes mkisofs directly for the ISO
  -> re-verifies generated input hashes
  -> publishes build log/report + artifact SHA-256 values
```

No GNU Make recipe, MSYS shell, `sh.exe`, global PATH mutation, or shell command composition is required. Child tools are invoked with explicit argument vectors and `shell=False`.

The first direct `build.bat` experiment was intentionally useful evidence: it proved the local SH-ELF compiler/linker and mkisofs command family can build the generated R1 project. The authoritative SRK path is now the Python driver so standalone builds use the same orchestration philosophy already adopted for controlled SAROO builds.

## Direct controller evidence used by the R1 host

The reviewed sample polls controller 1 by writing PDR1 in four phases:

```text
0x60
0x40
0x20
0x00
```

with a 16-NOP settle delay between phases. The packed sample is inverted with `0x8FFF` and exposes active-high buttons as:

```text
L      bit 15
START  bit 11
A      bit 10
C      bit 9
B      bit 8
RIGHT  bit 7
LEFT   bit 6
DOWN   bit 5
UP     bit 4
R      bit 3
X      bit 2
Y      bit 1
Z      bit 0
```

`srk_saturn_host.c` keeps the packed pre-inversion word as the diagnostic `raw_state` and converts the active-high sample into SRK's host-neutral button mask.

## Video/text host

R1 owns VDP2 because it is a standalone master-mode program. It configures NBG0 as the reviewed 8-bit bitmap surface, clears VDP2 VRAM/CRAM, installs a black/white palette, and uses the reviewed local `vga_font.h` only in the generated output tree.

The font is not committed to SRK. The preparation command copies it from the caller's reviewed local template while leaving that source file unchanged.

The host samples input once per application frame. Its microsecond-scale clock is frame-derived for R1: VDP2 `TVSTAT` selects PAL (`20000 us`) or NTSC (`16667 us`) cadence. A later timing diagnostic can replace this with independently measured hardware timing after the first boot/input milestone is physically established.

## IP.BIN policy

SRK does not commit a third-party Saturn IP.BIN. The caller supplies a reviewed local IP.BIN and SRK writes a separate patched copy into the generated project.

Only selected System ID fields are replaced:

```text
maker ID           SRK PROJECT
product number     SRK-DIAG
version            V0.001
release date       requested YYYYMMDD
area               JTUE
peripherals        J
title              SRK SATURN DIAGNOSTICS
first-read address 0x06004000
first-read size    0
```

The hardware ID, bootstrap/security payload, IP size, stack fields, reserved bytes, and all bytes beyond the System ID are preserved from the reviewed source asset.

## Prepare command

Example for the currently reviewed local environment:

```bat
python -m rikai_kotoba.tools.saturn_standalone_prepare ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --template "C:\Users\Developer.ERIDU\Saturn-Dev\SaturnOrbit-Inspect\payload\app\EXAMPLES\CharlesMacDonald\vdp1ex" ^
  --ip-bin "C:\Users\Developer.ERIDU\Saturn-Dev\SaturnOrbit-Inspect\payload\app\COMMON\IP.BIN" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1" ^
  --release-date 20261009
```

The output directory must not already exist. Preparation performs no compilation or packaging.

Generated shape:

```text
SRK-Diagnostics-R1/
  IP.BIN
  build.bat
  README_BUILD.txt
  SRK_STANDALONE_PROJECT.json
  srk_saturn.ld
  build/
  cd/
  src/
    vga_font.h
    srk_saturn_startup.S
    srk_saturn_main.c
    srk_saturn_host.c/.h
    srk_diag_*.c/.h
```

`build.bat` is now only a thin wrapper around the Python build command. It contains no compiler/linker/package recipe.

`SRK_STANDALONE_PROJECT.json` records source hashes, generated IP metadata, resolved tool paths, generated-file hashes, `build_orchestration = python-native`, and the no-build/no-SD-write policy state.

## Build boundary

After the generated tree and manifest are reviewed, the authoritative build command is:

```bat
python -m rikai_kotoba.tools.saturn_standalone_build ^
  --project "C:\path\to\SRK-Diagnostics-R1"
```

The Python build driver:

```text
verifies every generated input hash before execution
refuses pre-existing build outputs/provenance
invokes recorded tools directly with shell=False
keeps PATH unchanged
preserves -Wall -Werror
copies build/srk_diag.bin -> cd/0.bin using Python
creates build/srk_diag.iso
verifies generated inputs again after a successful build
writes SRK_STANDALONE_BUILD_LOG.txt
writes SRK_STANDALONE_BUILD.json
hashes the binary, ISO, linker map, and cd/0.bin
refuses a second Python-native build in the same generated tree
```

The SH-ELF tools are still responsible for code generation. Python is responsible for safe, deterministic orchestration and provenance.

A successful host build is not yet a physical Saturn validation. The generated binary/ISO and build report must be inspected before launch on hardware.
