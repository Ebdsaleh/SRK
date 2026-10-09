# SRK Standalone Saturn Environment Discovery

SRK must not invent a standalone Saturn CD build path from assumptions made by
the SAROO firmware build.  Before the first hardware host is generated, SRK
performs a read-only inventory of the user's real Saturn development tree.

The discovery command is:

```text
python -m rikai_kotoba.tools.saturn_standalone_probe \
  --saturn-root <Saturn development root>
```

An installed SRK package also exposes the equivalent
`srk-saturn-standalone-probe` console entry point.

## What the probe establishes

The report looks for concrete local evidence in five groups:

```text
SH-ELF compiler/object tools
SGL_302j tree and SL_DEF.H
static Saturn libraries
existing SAMPLE Makefiles and IP.BIN assets
make / ISO-builder / IP-builder helper programs
```

The SH-ELF compiler check reuses SRK's existing read-only toolchain resolver.
The additional standalone checks are deliberately evidence gathering rather than
a declaration that a CD image can already be built.

A complete-looking environment still requires selection and review of one actual
local sample/template before SRK creates a generated standalone project.  The
sample's startup object, linker script, libraries, controller path, video setup,
and IP.BIN/image construction steps must be understood rather than guessed.

## Safety and provenance

The probe:

- requires an explicit Saturn development root;
- does not modify that tree;
- does not modify the process or global `PATH`;
- may read `PATH` as a fallback when locating helper programs;
- bounds recursive discovery to avoid an accidental unbounded filesystem scan;
- caps the sample Makefiles displayed in one report;
- never builds, copies, flashes, burns, or deploys anything.

This preserves the same rule used throughout SRK: discovery and validation come
before mutation.

## Why this gate exists

Public Saturn examples demonstrate several viable approaches: bare SH-2 startup
and direct SMPC/VDP access, Sega SGL-based applications, and ISO construction
using an IP.BIN boot header.  Those examples are useful references, but SRK's
first standalone diagnostic build must use the assets that are actually present
and already workable on the user's development machine.

The first successful probe therefore does **not** close the standalone-host
milestone.  It tells the next tranche exactly which local build family can be
copied into a separate SRK-controlled generated tree and adapted to the
hardware-neutral diagnostic core.

## Next gate after a successful probe

After the real environment report is reviewed, SRK should choose the smallest
known-good local Saturn sample and create a separate generated project.  That
project will supply the host services required by `srk_diag_host.h`:

```text
monotonic time
direct controller sampling
raw + normalized pad state
minimal text/video output
current VBR observation
frame boundary
```

The first physical build remains intentionally narrow: boot the diagnostic menu,
exercise navigation and Controller / Input Test, prove L+R and hold timing, and
arm/freeze the in-RAM flight recorder.  SD writes, dumps, audio, 3D, and foreign
runtime injection remain later milestones.
