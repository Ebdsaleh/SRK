# Saturn Audio MIDI 68K Program Compiler Gate

This gate proves that SRK's protocol-only MC68EC000 program **representation**
can survive the exact legacy SH-ELF C compiler policy already accepted by the
standalone Saturn diagnostic.

It does **not** install or execute the MC68EC000 program.

## Input

The gate compiles:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_program.c
```

against:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_program.h
```

The source contains only the deterministic `unsigned short` word array for the
reviewed 162-byte protocol consumer image.

## Compiler policy

The same C flags as the standalone builder are used:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

Python invokes `sh-elf-gcc.exe` directly with an argv list and `shell=False`.
PATH is not changed.

## Safety boundary

This is compile-only evidence.

The gate performs no:

- link;
- startup assembly;
- ISO packaging;
- MODE1/2352 packaging;
- SAROO/card write;
- Sound RAM write;
- MC68EC000 program installation;
- reset SSP/PC change;
- SMPC command;
- SCSP register access;
- MC68EC000 execution.

The program remains constant SH-2-side data.

## Source integrity

The probe records SHA-256 for the C source and header before compilation and
requires both files to remain byte-identical afterward.

It also requires process PATH to remain unchanged.

A successful compiler return without a non-empty object file is not accepted as
a successful gate.

## Evidence directory

The output directory must not already exist.

A successful run contains:

```text
srk_saturn_midi_68k_program.o
SRK_MIDI_68K_COMPILE_PROBE_LOG.txt
SRK_MIDI_68K_COMPILE_PROBE.json
```

A compiler rejection still preserves the log/report evidence but does not
pretend an object exists.

## Command

From the SRK repository virtual environment:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-68K-COMPILE-GATE1"
```

Success is explicitly reported as:

```text
Result           : SUCCESS
Legacy SH-ELF GCC accepted the constant protocol-only MIDI 68K program representation.
```

## Next gate

After the real compiler accepts the constant program representation, SRK may
create a fresh full off-card standalone gate containing:

```text
generated MIDI data
+ SH-2 mailbox producer
+ protocol-only 68K program image
```

All three remain uncalled/uninstalled in that next gate.

Only after the complete build/link/package gate is accepted should SRK define
the bounded installer that copies the program into Sound RAM and changes the
MC68EC000 reset SSP/PC.

The first runtime 68K proof remains protocol-only and silent; SCSP note playback
is a later, separately gated tranche.
