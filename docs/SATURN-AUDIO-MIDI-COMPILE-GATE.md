# Saturn Audio MIDI Compiler Compatibility Gate

This gate exists between the generated MIDI hardware bridge and the real Saturn
standalone build.

It deliberately asks only one question:

> Does the exact legacy SH-ELF GCC backend used by SRK's Python-native Saturn
> build accept the inert generated MIDI C source under the same compile flags?

No runtime behavior is enabled by this gate.

## Why this gate exists

The generated MIDI bridge is intentionally old-toolchain-friendly C, but source
review alone is not enough. The legacy compiler is the authoritative test for
syntax, warning behavior and accepted C constructs.

Keeping this as a separate off-card proof means a compiler incompatibility
cannot be confused with linker, Sega SBL, ISO, SAROO, SCSP or MC68EC000 issues.

## Compile policy

The probe invokes the discovered `sh-elf-gcc` directly from Python using an argv
list and `shell=False`.

The C flags are the same flags currently used by the standalone builder:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The generated standalone integration directory is added only as the local
include path for `srk_saturn_midi_generated.h`.

The probe does **not**:

- invoke the linker;
- invoke the assembler;
- invoke `mkisofs`;
- mutate PATH;
- modify generated MIDI source/header files;
- touch a SAROO card;
- write Saturn Sound RAM;
- access SCSP MMIO;
- execute or replace the MC68EC000 program.

## Fresh-output rule

The requested output directory must not exist.

The probe creates a fresh off-card evidence directory containing:

```text
srk_saturn_midi_generated.o       when compilation succeeds
SRK_MIDI_COMPILE_PROBE_LOG.txt
SRK_MIDI_COMPILE_PROBE.json
```

A compiler failure is still preserved as evidence in the log/report; it does
not fall through to any later build stage.

## Provenance

Before compilation the probe SHA-256 hashes:

```text
integrations/saturn/standalone/srk_saturn_midi_generated.c
integrations/saturn/standalone/srk_saturn_midi_generated.h
```

It hashes them again after the compiler returns and requires both hashes to be
unchanged for a successful result.

It also snapshots the process PATH and requires that it remain unchanged.

## CLI

Example:

```bat
python -m rikai_kotoba.tools.saturn_midi_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-BRIDGE-COMPILE-GATE1"
```

The success boundary is:

```text
Result          : SUCCESS
Legacy SH-ELF GCC accepted the inert generated MIDI bridge.
```

## Next gate

Only after this compiler proof succeeds should the generated MIDI bridge be
added to the normal standalone-project source inventory and final link.

That later integration must remain behaviorally inert at first:

- no new menu control;
- no Sound RAM mailbox initialization;
- no queue publication;
- no 68K program replacement;
- no SCSP key-on caused by MIDI;
- no SAROO deployment.

Once the complete existing standalone image still builds with the inert object
linked in, the active SH-2/MC68EC000 mailbox implementation can begin as its own
separate tranche.
