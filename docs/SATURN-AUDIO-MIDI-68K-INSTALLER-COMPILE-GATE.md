# Saturn Audio MIDI — MC68EC000 Installer Compiler Gate

This gate validates the bounded SH-2-side installer source for the protocol-only
MC68EC000 MIDI consumer with the same legacy SH-ELF GCC backend and production C
policy used by the standalone Saturn diagnostic.

It is a compile-only compatibility proof. It does not install, launch, or execute
the MC68EC000 program.

## Input

The probe compiles:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_installer.c
```

with headers:

```text
srk_saturn_midi_68k_installer.h
srk_saturn_midi_68k_program.h
```

The reviewed installer remains responsible only for the bounded Sound-RAM copy
and read-back contract:

```text
program address  0x00000600
program words    81
program bytes    162
reset SSP        0x0007FFF0
reset PC         0x00000600
```

The installer requires the MC68EC000 to already be stopped. This compiler gate
does not establish that precondition and does not call the installer.

## Compiler policy

Python directly invokes the discovered `sh-elf-gcc.exe` with:

```text
-c
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The standalone integration directory is supplied as the include path.

The probe uses an argument vector, `shell=False`, and does not mutate `PATH`.

## Evidence policy

The output directory must not already exist.

Before invoking the compiler, the probe hashes:

- the installer C source;
- the installer header;
- the protocol-only 68K program header.

After compilation it hashes the inputs again. Success requires:

- compiler return code zero;
- a non-empty object file;
- all source/header hashes unchanged;
- `PATH` unchanged.

The fresh evidence directory contains:

```text
srk_saturn_midi_68k_installer.o
SRK_MIDI_68K_INSTALLER_COMPILE_PROBE_LOG.txt
SRK_MIDI_68K_INSTALLER_COMPILE_PROBE.json
```

A compiler rejection is preserved as evidence and returns failure without moving
to a link or hardware gate.

## Safety boundary

This probe performs no:

- linker invocation;
- startup assembly;
- ISO construction;
- MODE1/2352 packaging;
- SAROO write;
- Sound-RAM write;
- reset-vector write;
- mailbox publication;
- SMPC command;
- SCSP access;
- MC68EC000 program installation;
- MC68EC000 execution;
- installer call.

The source being compiled contains bounded hardware-access code, but compilation
cannot execute it.

## Source gate

Before running the real compiler probe, the repository test suite must be green
at the commit that introduced this gate.

Expected total after this tranche:

```text
491 tests
```

## Real compiler gate

With a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_installer_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-68K-INSTALLER-COMPILE-GATE1"
```

Success ends with:

```text
Result                    : SUCCESS
Legacy SH-ELF GCC accepted the bounded MIDI 68K installer.
```

## Next gate

After real-toolchain compile acceptance, the installer may be linked into another
fresh complete off-card standalone build alongside:

```text
generated MIDI event/tone data
+
SH-2 mailbox preload producer
+
protocol-only MC68EC000 program image
+
bounded MC68EC000 installer
```

The installer must remain uncalled in that full-build gate.

Only after that build/link/package proof may runtime orchestration be introduced
around the already accepted SMPC flow:

```text
safe command window
-> SNDOFF
-> install + verify
-> preload + verify
-> SNDON
```

The first real hardware execution remains silent and protocol-only. No audible
MIDI note is permitted until mailbox acknowledgement is proven.
