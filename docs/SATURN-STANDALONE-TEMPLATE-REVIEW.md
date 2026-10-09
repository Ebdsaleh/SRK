# SRK Standalone Saturn Template Review

The candidate-ranking probe identifies local Saturn projects worth inspecting.  A high score is not build approval.  Before SRK copies or adapts a project, one exact candidate is reviewed read-only at the file level.

The review command is:

```text
python -m rikai_kotoba.tools.saturn_standalone_template_probe \
  --candidate <exact project directory>
```

The probe reports:

```text
file size and SHA-256
file role
local IP.BIN metadata
bounded Makefile text
bounded linker-script text
bounded startup source
bounded controller/video/main source
```

It does not copy, compile, link, package, execute, or modify the candidate.

## Why the first target is vdp1ex

The wide local candidate report showed that `COMMON` scores highest because it colocates shared boot/build support, but it contains only one C source (`cinit.c`) and is better treated as infrastructure than as the first application template.

`EXAMPLES/CharlesMacDonald/vdp1ex` is the strongest small self-contained application candidate because the local directory already contains:

```text
Makefile
IP.BIN
source files
linker scripts
CRT0.S
main.c
smpc.c
conio.c
```

That combination is especially useful for SRK's first diagnostic host because the next milestone needs direct controller and minimal video/text services rather than a large gameplay sample.

This is still only a selection for review.  SRK must inspect the actual local Makefile, startup code, linker layout, SMPC path, text/video setup, and IP.BIN before generating a copy.

## Review order

Inspect `vdp1ex` first.  If its local build path is incomplete or incompatible with the installed SH-ELF toolchain, inspect `COMMON` and the best SGL sample next rather than editing the source tree or inventing missing commands.

After one template is accepted, SRK will create a separate generated project and keep the original installed example read-only.

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
