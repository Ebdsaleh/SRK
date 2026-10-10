# Saturn Audio — Silent MIDI 68K Physical-Proof Compiler Gate

This gate validates the bounded silent MC68EC000 physical-proof controller with
the real legacy SH-ELF GCC backend before any full-build or physical execution
step.

## Scope

Compiler input:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_physical_proof.c
```

Tracked headers:

```text
srk_saturn_midi_68k_physical_proof.h
srk_saturn_midi_68k_runtime.h
srk_saturn_midi_68k_hardware_adapter.h
```

Production flags:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

Python invokes the existing `sh-elf-gcc.exe` directly with argv,
`shell=False`, and an unchanged `PATH`.

## What this proves

A successful gate proves only that the SH-2-side physical-proof controller is
accepted by the legacy compiler under the same C policy used by the standalone
build.

The controller's intended runtime seam is:

```text
physical proof controller
-> adapter-neutral runtime
-> Saturn hardware adapter
```

The controller remains uncalled in this gate.

## What this does not do

The compile gate does not:

- link the controller;
- assemble startup code;
- build an ISO or MODE1/2352 image;
- call the physical-proof controller;
- call the runtime or hardware adapter;
- issue `SNDOFF` or `SNDON`;
- access Saturn Sound RAM at runtime;
- alter reset vectors;
- publish the MIDI mailbox;
- install or execute MC68EC000 code;
- access SCSP registers;
- touch SAROO/card media.

The source and all tracked headers are SHA-256 hashed before and after the
compiler invocation. The output directory must not already exist.

## Run

From the SRK virtual environment:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_physical_proof_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-68K-PHYSICAL-PROOF-COMPILE-GATE1"
```

Expected success boundary:

```text
Result                    : SUCCESS
Legacy SH-ELF GCC accepted the silent MIDI 68K physical-proof controller.
```

Evidence written to the fresh output directory:

```text
srk_saturn_midi_68k_physical_proof.o
SRK_MIDI_68K_PHYSICAL_PROOF_COMPILE_PROBE_LOG.txt
SRK_MIDI_68K_PHYSICAL_PROOF_COMPILE_PROBE.json
```

If the compiler returns non-zero, preserve the evidence directory and stop.
Do not proceed to the physical-proof full-build gate.

## Next gate

After compiler success, the next tranche is a fresh complete off-card
standalone build containing the already accepted MIDI/68K stack plus the
physical-proof controller, still linked but uncalled.

Only after that full-build gate passes may SRK add an explicit diagnostic input
and telemetry binding for an R18 candidate.

The first real-Saturn execution remains silent. Physical success is only:

```text
READY set
READ_SEQUENCE == 1
READ_INDEX == 1
LAST_ERROR == 0
```

No MIDI-driven SCSP note is attempted until that round trip is accepted on
hardware.
