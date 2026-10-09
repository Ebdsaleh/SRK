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
SD writes from Saturn runtime
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

"Python-native build" does **not** mean Python replaces the SH-2 compiler. SRK still needs the reviewed `sh-elf-gcc`/`sh-elf-as` toolchain to translate C/assembly into SH-2 machine code, and still uses the reviewed ISO builder for the ISO9660 data-track payload.

Python replaces the fragile orchestration layer:

```text
Python
  -> verifies generated input hashes
  -> invokes sh-elf-gcc directly for each C source
  -> invokes sh-elf-as directly for startup
  -> invokes sh-elf-gcc directly for the final link
  -> copies the first-read binary with Python file I/O
  -> invokes mkisofs directly for the ISO9660 payload
  -> converts that payload to verified MODE1/2352 BIN/CUE
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

## BIN/CUE packaging boundary

The Saturn optical drive reads CD sectors; it does not consume a PC `.iso` filename. `mkisofs` is retained because it is a convenient reviewed way to construct the ISO9660 **2048-byte user-data payload**. For SAROO deployment, SRK then reframes every logical sector as a complete CD-ROM Mode 1 raw sector:

```text
12 sync
 4 header (BCD MSF + mode 1)
2048 user data
 4 EDC
 8 zero/reserved
276 ECC P/Q
----------------
2352 bytes per sector
```

The header address uses `LBA + 150` frames. EDC is generated over bytes `0x000-0x80F`; ECC-P is written before ECC-Q because Q covers the P parity region.

The Python converter verifies every generated 2352-byte sector by reconstructing it from the original 2048-byte ISO sector and requiring an exact byte match. It also refuses to overwrite an existing BIN or CUE.

A successful standalone build therefore contains:

```text
build/srk_diag.bin
    linked SH-2 first-read program; NOT a disc image

build/srk_diag.iso
    internal 2048-byte-sector ISO9660 verification/intermediate artifact

build/SRK-Diagnostics/
    SRK-Diagnostics.bin
    SRK-Diagnostics.cue
```

The deployable pair is:

```text
FILE "SRK-Diagnostics.bin" BINARY
  TRACK 01 MODE1/2352
    INDEX 01 00:00:00
```

Only the `build/SRK-Diagnostics` BIN/CUE pair is intended for the SAROO game-image directory. The linked `build/srk_diag.bin` must never be mistaken for a raw CD image.

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
converts the ISO payload to a verified single-track MODE1/2352 BIN/CUE pair
verifies generated inputs again after a successful build
writes SRK_STANDALONE_BUILD_LOG.txt
writes SRK_STANDALONE_BUILD.json
hashes the linked binary, ISO, map, cd/0.bin, raw BIN, and CUE
records the deployable BIN/CUE paths and sector counts in the build report
refuses a second Python-native build in the same generated tree
```

The SH-ELF tools are still responsible for code generation. Python is responsible for safe, deterministic orchestration, raw-disc framing, verification, and provenance.

## Guarded SAROO deployment boundary

After the BIN/CUE and build report have been reviewed, deployment is a separate guarded operation. The default command is read-only:

```bat
python -m rikai_kotoba.tools.saturn_saroo_deploy ^
  --card-root "D:\" ^
  --project "C:\path\to\SRK-Diagnostics-R1"
```

Before proposing any write, SRK:

```text
requires a successful standalone build report
requires deployable format cue-bin-mode1-2352
requires verified_against_iso = true
re-hashes the BIN and CUE against the accepted build report
re-verifies every MODE1/2352 raw sector against build/srk_diag.iso
requires an unambiguous modern SAROO layout
requires an existing SAROO/ISO directory
requires the destination game directory to be absent
refuses an existing pending deployment directory
```

The write path requires the explicit token:

```text
DEPLOY-SATURN-IMAGE
```

SRK first copies the two files to a new hidden pending directory, verifies their size and SHA-256, and only then renames that directory to the final game directory. On a copy/verification failure the pending directory is removed. Existing SAROO game directories are never merged, overwritten, renamed, or removed.

The first physical R1 deployment therefore changes only one new directory beneath `SAROO/ISO` and contains only the verified `SRK-Diagnostics.bin` and `SRK-Diagnostics.cue` pair.

A successful host build or card deployment is not yet a physical Saturn validation. The first hardware acceptance remains: boot, visible menu, UP/DOWN navigation, A selection, START return, raw/normalized input, simultaneous L+R timing, and in-RAM flight-recorder arm/freeze.
