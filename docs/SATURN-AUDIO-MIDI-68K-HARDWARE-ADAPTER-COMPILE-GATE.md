# Saturn Audio MIDI — MC68EC000 Hardware Adapter Compiler Gate

## Purpose

This gate validates that the silent Saturn MIDI MC68EC000 hardware adapter is
accepted by the real legacy SH-ELF GCC backend used by SRK's standalone Saturn
build.

The adapter remains completely uncalled in this tranche. The gate performs a
single compile-only operation and does not link or execute any Saturn runtime
path.

## Inputs

The probe compiles:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_hardware_adapter.c
```

against the committed headers:

```text
srk_saturn_midi_68k_hardware_adapter.h
srk_saturn_midi_68k_runtime.h
srk_saturn_midi_68k_installer.h
srk_saturn_midi_mailbox.h
srk_saturn_midi_generated.h
```

All six source/header inputs are SHA-256 hashed before and after the compiler
invocation.

## Compiler policy

The probe uses Python-native orchestration and invokes the discovered
`sh-elf-gcc.exe` directly with an argv list and `shell=False`.

Pinned C flags:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The process PATH is not modified.

## Safety boundary

The adapter source contains the already-reviewed Saturn SMPC and Sound-RAM MMIO
operations, but compiling that source does not execute them.

This gate does not:

- link a Saturn binary;
- assemble startup code;
- create an ISO or BIN/CUE image;
- call the hardware adapter;
- call the runtime orchestrator;
- issue SNDON or SNDOFF;
- write or read Saturn Sound RAM at runtime;
- change MC68EC000 reset vectors;
- publish the MIDI mailbox;
- install or execute the MC68EC000 program;
- touch SCSP MMIO;
- write to SAROO or any SD card.

The report deliberately distinguishes `hardware_adapter_present=true` from
`hardware_adapter_called=false`.

## Success requirements

`SUCCESS` requires all of the following:

1. the real legacy SH-ELF compiler returns zero;
2. a non-empty object file is produced;
3. every source/header input hash is unchanged;
4. the process PATH is unchanged.

A compiler rejection is preserved in the fresh evidence directory and must stop
the tranche before any full-build gate.

## Command

From the SRK repository with the virtual environment active:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_hardware_adapter_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-68K-HARDWARE-ADAPTER-COMPILE-GATE1"
```

The output directory must not already exist.

## Expected terminal boundary

```text
Result                    : SUCCESS
Legacy SH-ELF GCC accepted the silent Saturn MIDI 68K hardware adapter.
```

## Next gate

After compiler acceptance, the adapter may be linked into a fresh complete
off-card standalone build together with the already accepted MIDI/68K stack.
It must remain uncalled in that full-build gate.

Only after source, compiler, and full-build acceptance may SRK define the first
bounded physical protocol-proof control path that actually supplies the adapter
to `srk_saturn_midi_68k_protocol_begin()`.

The first physical proof remains silent and protocol-only. No MIDI-driven SCSP
note is permitted until the MC68EC000 mailbox acknowledgement is proven on real
hardware.
