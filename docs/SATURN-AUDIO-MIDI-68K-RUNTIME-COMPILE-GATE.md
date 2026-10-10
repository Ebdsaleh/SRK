# Saturn Audio — Silent MIDI 68K Runtime Compiler Gate

## Purpose

This gate validates that the adapter-neutral silent MIDI/MC68EC000 runtime
orchestrator is accepted by the same legacy SH-ELF GCC backend used by SRK's
standalone Saturn diagnostic.

It compiles only:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_runtime.c
```

against:

```text
srk_saturn_midi_68k_runtime.h
srk_saturn_midi_generated.h
srk_saturn_midi_mailbox.h
```

The runtime remains uncalled and no Saturn hardware adapter is present in this
tranche.

## Production C policy

The probe uses the standalone C flags:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

Python owns orchestration and invokes `sh-elf-gcc.exe` directly with an argv
list, `shell=False`, and without mutating PATH.

## What this proves

A successful gate proves only that the legacy SH-ELF compiler accepts the C89
representation of the adapter-neutral runtime protocol layer.

The runtime contract remains:

```text
validate operations
-> stop sound CPU
-> install + verify program
-> publish preload
-> verify preload
-> start sound CPU
-> RUNNING
```

The non-blocking poll classifies the protocol as `ACKNOWLEDGED` only when:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     1
LAST_ERROR     0
```

A non-zero `LAST_ERROR` is `CONSUMER_ERROR`; an incomplete, error-free state is
still `RUNNING`.

## What this does not prove

This compiler gate does **not** prove:

- link compatibility with the complete standalone image;
- SMPC command execution;
- Sound-RAM access;
- reset-vector changes;
- mailbox publication;
- MC68EC000 execution;
- SCSP behavior;
- MIDI sound output;
- SAROO deployment.

Those remain separate gates.

## Safety boundary

The compile probe:

- requires a fresh off-card output directory;
- hashes the runtime source and all directly included SRK headers before and
  after compilation;
- requires source inputs to remain unchanged;
- requires PATH to remain unchanged;
- preserves compiler output and a JSON report;
- performs no link, startup assembly, ISO build, or MODE1/2352 packaging;
- performs no SD-card write;
- has no hardware adapter and calls no runtime path.

## Command

After the source suite is green:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_runtime_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-MIDI-68K-RUNTIME-COMPILE-GATE1"
```

The output directory must not already exist.

Expected success boundary:

```text
Result                    : SUCCESS
Legacy SH-ELF GCC accepted the adapter-neutral silent MIDI 68K runtime.
```

On failure, preserve the fresh evidence directory and do not proceed to a full
build.

## Next gate

After compiler acceptance, the adapter-neutral runtime should be linked into a
fresh complete off-card standalone image while remaining uncalled and without a
hardware adapter.  Only after that complete build passes should SRK introduce
the Saturn hardware adapter implementing the already accepted SMPC/Sound-RAM
flow.

No R18 card deployment is authorized by this gate.
