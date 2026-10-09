# SRK Standalone Saturn Template Review

The candidate-ranking probe identifies local Saturn projects worth inspecting. A high score is not build approval. Before SRK copies or adapts a project, one exact candidate is reviewed read-only at the file level.

The review command is:

```text
python -m rikai_kotoba.tools.saturn_standalone_template_probe \
  --candidate <exact project directory>
```

The probe reports:

```text
file size and SHA-256
file role
local Saturn System ID / IP.BIN metadata
bounded Makefile and build-list text
bounded script text
bounded linker-script text
bounded startup source
bounded controller/video/main source
```

It does not copy, compile, link, package, execute, or modify the candidate.

## Why the first target is vdp1ex

The wide local candidate report showed that `COMMON` scores highest because it colocates shared boot/build support, but it contains only one C source (`cinit.c`) and is better treated as infrastructure than as the first application template.

`EXAMPLES/CharlesMacDonald/vdp1ex` is the strongest small self-contained application candidate because the local directory contains:

```text
Makefile
IP.BIN
source files
linker script
CRT0.S
main.c
smpc.c
conio.c
vdp.c / vdp.h
```

That combination is especially useful for SRK's first diagnostic host because the next milestone needs direct controller and minimal video/text services rather than a large gameplay sample.

## First real vdp1ex review

Read-only inspection of the user's installed `vdp1ex` established several concrete facts.

### Startup and load layout

`BART.LNK` is a real GNU linker script. It emits a plain binary image beginning at:

```text
0x06004000
```

Its layout is:

```text
.text
.rodata
.data
.bss
```

`CRT0.S` is intended to be linked first. It:

```text
clears BSS
sets r15 to 0x06004000
uses 0x06002000-0x06003FFF as the documented stack region
calls __main
```

The historical template jumps to `0x02000100` if `__main` returns, because this example was also intended for Action Replay cartridge development. SRK must not inherit that exit behavior blindly for a CD/SAROO-launched standalone application.

### Direct controller path

The template performs direct Saturn controller-port I/O rather than reading a BIOS-maintained controller snapshot.

It configures:

```text
PDR1 / PDR2
DDR1 / DDR2
IOSEL
EXLE
```

and reads controller 1 in four manual phases before returning an active-high button mask.

The observed mask contract is:

```text
L      1 << 15
START  1 << 11
A      1 << 10
C      1 << 9
B      1 << 8
RIGHT  1 << 7
LEFT   1 << 6
DOWN   1 << 5
UP     1 << 4
R      1 << 3
X      1 << 2
Y      1 << 1
Z      1 << 0
```

This is strong source evidence for the standalone Input Test, but it still requires physical validation on SRK's own host.

The historical `pad_read(int which)` implementation currently reads `PDR1` regardless of `which`, so it should be treated as a controller-1 routine rather than a generic multi-port implementation.

### Minimal text/video path

`vdp_init()` configures VDP2 NBG0 as a 256-color bitmap backed by VDP2 VRAM, clears VRAM/CRAM, and provides polling helpers for HBLANK/VBLANK state.

`conio.c` installs a 256-entry palette and renders an 8x8 bitmap font by writing pixels directly into the VDP2 bitmap. This is a good minimal reference for the first SRK diagnostic menu because it avoids pulling in a larger SGL renderer.

### Historical dependencies that must not be copied blindly

The local `main.c` contains a hardcoded SH-COFF `stdlib.h` include described by the source itself as a "dirty fix". SRK's first host is targeting the already-proven SH-ELF toolchain, so this path must not be inherited.

The candidate Makefile is only:

```text
include ./objects
include C:/SaturnOrbit/COMMON/mf_CMD
```

Therefore the exact build command still depends on two pieces that must be reviewed:

```text
OBJECTS
COMMON/mf_CMD
```

The local directory also contains `MAKE_COF.bat.lnk` and `MAKE_ELF.bat.lnk`. These are Windows Shell Link shortcut files, not linker scripts. The template probe now identifies Shell Links separately and does not decode their binary contents as build text.

## Saturn System ID correction

The first version of SRK's IP.BIN metadata parser used an incorrect field layout. The real `vdp1ex` IP.BIN made the bug visible because fields appeared shifted into one another.

Saturn System ID text fields are now parsed using the Saturn layout:

```text
0x00  hardware ID       16 bytes
0x10  maker ID          16 bytes
0x20  product number    10 bytes
0x2A  version            6 bytes
0x30  release date       8 bytes
0x38  device info        8 bytes
0x40  area symbols      10 bytes
0x4A  space              6 bytes
0x50  peripherals       16 bytes
0x60  game title       112 bytes
```

The boot-control words are also exposed read-only:

```text
0xE0  IP size
0xE8  master stack
0xEC  slave stack
0xF0  first-read address
0xF4  first-read size
```

They are decoded as big-endian 32-bit values.

`game_serial` remains a compatibility alias for `product_number`.

## Build-asset review improvements

The template inspector now treats these as reviewable build text:

```text
OBJECTS
run.bat / .cmd scripts
mf_* make fragments
```

and distinguishes actual textual `.LNK` linker scripts from binary Windows `.lnk` shortcuts by validating the Shell Link header.

This keeps the review evidence accurate before any generated standalone tree is created.

## Next review gate

Before SRK creates a standalone project, rerun `vdp1ex` with enough text budget to include the complete `main.c`, then inspect the shared `COMMON` directory that supplies `mf_CMD`.

```text
python -m rikai_kotoba.tools.saturn_standalone_template_probe \
  --candidate <vdp1ex> \
  --max-lines 500

python -m rikai_kotoba.tools.saturn_standalone_template_probe \
  --candidate <COMMON> \
  --max-lines 500
```

The resulting evidence must establish:

```text
exact OBJECTS contents
exact mf_CMD compiler/link commands
actual SH-ELF flags
startup object ordering
output filename and format
IP.BIN / first-read relationship
disc-image construction command
full vdp1ex initialization / frame loop
```

Only after those are understood will SRK create a separate generated project. The original installed example remains read-only.

The first generated host remains deliberately narrow:

```text
boot
menu text
UP / DOWN
A select
START return
raw controller word
normalized buttons
L+R hold timing
in-RAM flight-recorder arm/freeze
```

SD writes, memory dumps, audio, 3D, and foreign-runtime injection remain later milestones.
