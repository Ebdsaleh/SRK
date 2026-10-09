# SRK Standalone Saturn Candidate Ranking

The broad standalone-environment probe established that the user's Saturn development tree contains a working SH-ELF compiler set, a Sega SGL tree, Saturn sample Makefiles, existing IP.BIN assets, and mkisofs.

The next gate is still read-only: identify which concrete local project directory carries the strongest evidence of being a complete Saturn standalone build template.

Run:

```text
python -m rikai_kotoba.tools.saturn_standalone_candidate_probe \
  --saturn-root <Saturn development root>
```

The installed console entry point is `srk-saturn-standalone-candidates`.

## Why a second probe is needed

The first environment report intentionally treated every `SAMPLE` Makefile as evidence. That included generic Renesas SH evaluation-board examples which use the same compiler but are not Saturn boot projects.

The wider Saturn tree also contains `EXAMPLES` projects with IP.BIN files. Those are potentially much better templates because a project that colocates source, Makefile, boot header, linker/startup evidence, and ISO construction commands is closer to the actual standalone path SRK needs.

The candidate probe therefore ranks directories by evidence such as:

```text
Makefile
local IP.BIN
C / assembly source
linker script
startup object/source
EXAMPLES or SGL SAMPLE location
sh-elf build commands
mkisofs / generic-boot commands
SGL linkage references
```

Generic `SH_ELF/Samples/EVB*` and `SH_ELF/Samples/SE*` projects remain visible but receive a ranking penalty because they are processor/evaluation-board samples, not Saturn boot evidence.

## Library discovery correction

Historical SaturnOrbit SGL installations commonly use directory names such as `LIB_ELF` and `LIB_COFF`, not just `LIB` or `LIB32`.

The candidate probe therefore treats any path component beginning with `lib` as a possible library directory and reports `.A` / `.LIB` artifacts plus support objects such as `cinit.o` and `sglarea.o`.

This is deliberately a discovery improvement rather than a claim that any located library is already compatible with the selected compiler or project.

## Safety

The candidate probe:

- reads only beneath the explicit Saturn development root;
- does not copy or modify SDK/sample files;
- does not execute Makefiles;
- does not build an executable or ISO;
- does not modify PATH;
- does not touch SAROO or the SD card;
- bounds recursive traversal and the number of candidates returned.

A high score means only "inspect this local template first".

## Next gate

After the real machine reports its ranked candidates, SRK should inspect the top candidate's exact Makefile, startup/linker inputs, controller/video path, IP.BIN relationship, and ISO command.

Only after that inspection should SRK create a separate generated standalone project and connect the hardware-neutral diagnostic core through `srk_diag_host.h`.
