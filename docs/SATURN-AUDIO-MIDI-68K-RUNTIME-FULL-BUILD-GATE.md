# Saturn Audio MIDI — Adapter-Neutral 68K Runtime Full-Build Gate

## Status

This document defines the off-card full-build gate for SRK's adapter-neutral,
silent MIDI MC68EC000 runtime orchestrator.

This gate is intentionally still pre-runtime.  It proves that the complete
pre-runtime MIDI stack plus the orchestration layer survives the normal Saturn
standalone build, while the orchestration layer remains uncalled and no Saturn
hardware adapter is present.

## Proven input boundary

The gate is layered on the previously accepted components:

```text
SMF diagnostic asset
-> deterministic SRKM event program
-> generated event/tone C data
-> SH-2 mailbox preload producer
-> protocol-only MC68EC000 program image
-> bounded MC68EC000 installer
-> adapter-neutral silent runtime orchestrator
```

The first six layers already have independent source/compiler/full-build proof
as applicable.  This gate adds only the final adapter-neutral runtime layer to a
fresh complete image.

## Accepted orchestration contract

The runtime operation table is:

```text
stop_sound_cpu
install_program
publish_preload
verify_preload
start_sound_cpu
read_mailbox_word
```

The begin path is locked to:

```text
validate operations
-> stop sound CPU
-> install + verify 68K program
-> publish deterministic preload
-> verify preload
-> start sound CPU
-> RUNNING
```

The poll path is non-blocking and reads only:

```text
flags
read_sequence
read_index
last_error
```

The silent protocol proof is acknowledged only when:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     1
LAST_ERROR     0
```

A non-zero `LAST_ERROR` is classified as `CONSUMER_ERROR`.

## Why no hardware adapter is present

The runtime layer intentionally does not know how Saturn hardware is accessed.
It has no direct:

```text
SMPC COMREG address
SMPC SF address
VDP2 TVSTAT address
Sound-RAM aperture
SCSP aperture
```

This keeps sequencing failures independent from hardware-MMIO failures.

The later Saturn adapter must bind the operation table to the already accepted
hardware behavior.  That adapter is a separate gate and is not part of this
one.

## Fresh-tree derivation

The gate always starts from the accepted Stage-6B Gate-5 project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5
```

The baseline is verified and never modified.

The gate re-applies, in order:

1. inert generated MIDI event/tone data;
2. uncalled SH-2 mailbox preload producer;
3. uninstalled protocol-only MC68EC000 image;
4. uncalled bounded MC68EC000 installer;
5. uncalled adapter-neutral silent runtime.

The fresh project receives:

```text
src\srk_saturn_midi_68k_runtime.c
src\srk_saturn_midi_68k_runtime.h
```

For this proof only, the runtime C source is appended to the fresh copied:

```text
src\srk_saturn_runtime.c
```

This lets the unchanged normal Python-native standalone builder compile and
link the runtime layer without changing production standalone source lists.

## Required manifest safety state

The derived manifest must record:

```text
midi_bridge_active               false
midi_mailbox_producer_linked     true
midi_mailbox_producer_called     false
midi_68k_program_linked          true
midi_68k_program_installed       false
midi_68k_installer_linked        true
midi_68k_installer_called        false
midi_68k_runtime_linked          true
midi_68k_runtime_called          false
midi_68k_hardware_adapter_present false
midi_68k_reset_vectors_changed   false
midi_sound_ram_writes            false
midi_scsp_mmio                   false
midi_smpc_commands               false
midi_mc68ec000_execution         false
```

The runtime C can describe orchestration, but no operation table is supplied by
the production diagnostic in this gate and no call site exists.

## Source gate

The tranche adds four regression tests.

Expected total:

```text
508 tests
```

Run:

```bat
cd /d C:\Users\Developer.ERIDU\repos\Python\SRK
.venv\Scripts\activate

git status
git pull --ff-only
git log -4 --oneline
git rev-parse HEAD

python -m unittest discover -s tests -p "test_*.py"
python -m pytest -q
python -m pytest
```

All three test paths must be green before the real full-build gate is run.

## Real full-build gate

Use a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_runtime_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-RUNTIME-INERT-FULL-GATE1"
```

Expected state:

```text
Producer linked       : YES
Producer called       : NO
68K image linked      : YES
68K installed         : NO
Installer linked      : YES
Installer called      : NO
Runtime linked        : YES
Runtime called        : NO
Hardware adapter      : NO
68K executed          : NO
Bridge active         : NO
Result                : SUCCESS
```

Every normal build step must return zero:

```text
C compilation
startup assembly
mixed-format link
ISO package
packaged-PCM verification
MODE1/2352 BIN/CUE package
```

The packaged PCM payload must remain exact.

## Safety boundary

This gate performs no:

- runtime call;
- hardware adapter binding;
- SMPC command;
- Sound-RAM runtime write;
- reset-vector change;
- SCSP access;
- MC68EC000 execution;
- SAROO/card write;
- physical control binding.

No R18 deployment is authorized by this gate.

## Next gate

After full-build success, add the Saturn hardware adapter around the already
accepted hardware sequence:

```text
safe command window
-> SNDOFF
-> bounded install + exact read-back verify
-> deterministic preload + exact verify
-> SNDON
-> non-blocking mailbox poll
```

The adapter must be source-gated, compiled by the real legacy SH-ELF backend,
and full-build-gated while still uncalled before a physical menu/control path is
added.

The first physical MC68EC000 execution proof remains silent and protocol-only.
No MIDI-driven SCSP note is attempted until mailbox acknowledgement is proven on
real hardware.

> Safer is secure, secure is faster.
