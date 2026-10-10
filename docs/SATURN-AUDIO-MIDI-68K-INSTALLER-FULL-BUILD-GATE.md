# Saturn Audio MIDI — MC68EC000 Installer Full-Build Gate

## Purpose

This gate proves that the complete pre-runtime MIDI stack, including the bounded
MC68EC000 installer, survives the normal Saturn standalone compile/link/package
pipeline while remaining behaviorally inactive.

The gate contains:

```text
canonical MIDI event/tone data
+
uncalled SH-2 mailbox preload producer
+
uninstalled protocol-only MC68EC000 program image
+
uncalled bounded MC68EC000 installer
```

It does **not** execute any of those runtime paths.

## Baseline

The gate derives from an already-successful standalone Stage-6B project and
never mutates that baseline.

The normal reference remains:

```text
SRK-Diagnostics-R1-STAGE6B-GFS-GATE5
```

Before deriving a fresh tree, the lower-level gate chain verifies the baseline
manifest, accepted build report, and every pinned generated input.

## Fresh-tree derivation

The gate re-applies the already-reviewed layers in order:

1. inert generated MIDI event/tone bridge;
2. uncalled SH-2 mailbox preload producer;
3. uninstalled protocol-only MC68EC000 program image;
4. uncalled bounded MC68EC000 installer.

For this proof only, each C implementation is appended to the fresh copied
`src/srk_saturn_runtime.c` so the unchanged normal Python-native standalone
builder compiles and links the complete set.

The fresh tree also retains individual source/header copies for provenance.

## Installer contract

The installer is restricted to the already-reviewed protocol image:

```text
program address  0x00000600
program words    81
program bytes    162
stack value      0x0007FFF0
reset SSP addr   0x00000000
reset PC addr    0x00000004
```

The installer source owns these entry points:

```text
srk_saturn_midi_68k_install_while_stopped()
srk_saturn_midi_68k_verify_install()
```

Its critical runtime precondition remains:

```text
MC68EC000 must already be stopped.
```

This gate does not satisfy that precondition because the installer is never
called.

## Safety policy

The derived manifest must record:

```text
midi_bridge_active             false
midi_mailbox_producer_linked   true
midi_mailbox_producer_called   false
midi_68k_program_linked        true
midi_68k_program_installed     false
midi_68k_installer_linked      true
midi_68k_installer_called      false
midi_68k_reset_vectors_changed false
midi_sound_ram_writes          false
midi_scsp_mmio                 false
midi_smpc_commands             false
midi_mc68ec000_execution       false
```

Therefore this gate performs no runtime Sound-RAM write, reset-vector change,
SCSP access, SMPC command, MC68EC000 execution, or SAROO write.

## Build path

The normal Python-native standalone builder must complete all existing stages:

```text
C compilation
startup assembly
mixed-format link
ISO packaging
packaged-PCM verification
MODE1/2352 BIN/CUE packaging
```

No Make-based orchestration is introduced. Python continues to invoke the
existing SH-ELF compiler/assembler/linker backend and ISO tooling directly.

## Expected CLI

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_installer_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-INSTALLER-INERT-FULL-GATE1"
```

The output directory must not already exist.

## Success boundary

A successful gate must report:

```text
Producer linked       : YES
Producer called       : NO
68K image linked      : YES
68K installed         : NO
Installer linked      : YES
Installer called      : NO
68K executed          : NO
Bridge active         : NO
Result                : SUCCESS
```

All normal build commands must return zero and the packaged PCM proof must remain
exact.

## What this gate proves

A successful result proves that the complete pre-runtime MIDI/MC68EC000 stack
can coexist in the final Saturn binary without changing runtime behavior.

It does **not** prove:

- Sound RAM installation;
- reset-vector publication;
- mailbox publication;
- SMPC sound-CPU stop/start sequencing;
- MC68EC000 execution;
- mailbox acknowledgement;
- MIDI-driven SCSP sound.

## Next gate

Only after this full-build gate succeeds should SRK add runtime orchestration
around the already accepted Saturn audio SMPC sequence:

```text
safe SMPC command window
-> SNDOFF
-> bounded 68K install + read-back verify
-> deterministic mailbox/tone preload + verify
-> SNDON
```

The first real-hardware execution tranche remains **silent/protocol-only**. It
must prove MC68EC000 mailbox acknowledgement before any MIDI event is allowed to
drive an SCSP slot.

No R18 card deployment is authorized merely by this build gate.
