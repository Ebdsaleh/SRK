# Saturn Audio MIDI Mailbox Compiler Gate

This gate validates the first hardware-shaped SH-2 MIDI preload producer against
the same legacy SH-ELF GCC backend and C policy used by SRK's standalone Saturn
builder.

It remains an **off-card, compile-only gate**. The producer is not called.

## Inputs

The compiler consumes:

```text
integrations/saturn/standalone/srk_saturn_midi_mailbox.c
integrations/saturn/standalone/srk_saturn_midi_mailbox.h
integrations/saturn/standalone/srk_saturn_midi_generated.h
```

The generated MIDI C data has already passed its own real-toolchain compile gate
and a complete inert standalone build/link/package gate.

## Production C policy

The probe uses:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The standalone integration directory is supplied as the include path.

Python owns orchestration. The compiler is invoked directly with an argv list,
`shell=False`, and PATH is not modified.

## Safety boundary

Even though `srk_saturn_midi_mailbox.c` contains Sound-RAM access code, compiling
it cannot execute those accesses.

The gate performs no:

- link;
- startup assembly;
- ISO build;
- MODE1/2352 package;
- SAROO write;
- Sound RAM write;
- SCSP MMIO;
- SMPC command;
- MC68EC000 execution;
- call to `srk_saturn_midi_preload_publish()`.

Source/header SHA-256 values are checked before and after the compiler process.
The process must also leave PATH unchanged and produce a non-empty object.

## Fresh-output policy

The probe refuses to merge into an existing output directory.

On success the directory contains:

```text
srk_saturn_midi_mailbox.o
SRK_MIDI_MAILBOX_COMPILE_PROBE_LOG.txt
SRK_MIDI_MAILBOX_COMPILE_PROBE.json
```

A compiler rejection is preserved as evidence and stops at this gate.

## Command

From the SRK virtual environment:

```bat
python -m rikai_kotoba.tools.saturn_midi_mailbox_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-MAILBOX-COMPILE-GATE1"
```

The output directory must not already exist.

## Success boundary

```text
Result                : SUCCESS
Legacy SH-ELF GCC accepted the inert MIDI preload producer.
```

Only after this succeeds should the producer and generated MIDI data be linked
together in another fresh, complete standalone off-card build while the producer
remains uncalled.

The MC68EC000 consumer comes after that full-build gate, not before.
