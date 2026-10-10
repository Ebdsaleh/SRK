# Saturn Audio MIDI MC68EC000 Hardware-Adapter Full-Build Gate

## Purpose

This gate proves that the complete silent Saturn MIDI/MC68EC000 stack can pass
through the normal Python-native standalone build with the real Saturn hardware
adapter linked in while remaining completely uncalled.

The gate contains:

```text
generated MIDI event/tone data
+ SH-2 mailbox preload producer
+ protocol-only MC68EC000 program image
+ bounded MC68EC000 installer
+ adapter-neutral runtime orchestrator
+ Saturn hardware adapter
```

This is the last full-build compatibility proof before SRK may define a physical
silent protocol-execution path.

## Baseline

The gate derives from the already accepted Stage-6B Gate-5 standalone project.
The baseline tree is never modified. The output directory must not already
exist.

The derivation reuses every previously accepted inert MIDI/68K full-build layer,
then adds the hardware adapter as the final linked but uncalled layer.

## Hardware adapter

The adapter reproduces the already accepted standalone Audio behavior:

```text
SMPC COMREG     0x2010001F
SMPC SF         0x20100063
VDP2 TVSTAT     0x25F80004
Sound RAM       0x25A00000
SNDON           0x06
SNDOFF          0x07
SMPC timeout    1000000
```

It supplies the six operations required by
`SRK_SATURN_MIDI_68K_RUNTIME_OPS`:

```text
stop_sound_cpu
install_program
publish_preload
verify_preload
start_sound_cpu
read_mailbox_word
```

No SCSP aperture is present in this adapter.

## Inert build mechanism

For this compatibility proof only, the committed hardware-adapter C source is
copied into the fresh derived tree and appended to the fresh copied
`src/srk_saturn_runtime.c`. This lets the unchanged normal standalone builder
compile and link the adapter without introducing an active production call.

The adapter header/source are also copied separately into `src/` and pinned by
SHA-256 in the derived manifest.

## Required manifest state

The full-build gate records at least:

```text
midi_bridge_active                 false
midi_mailbox_producer_linked       true
midi_mailbox_producer_called       false
midi_68k_program_linked            true
midi_68k_program_installed         false
midi_68k_installer_linked          true
midi_68k_installer_called          false
midi_68k_runtime_linked            true
midi_68k_runtime_called            false
midi_68k_hardware_adapter_present  true
midi_68k_hardware_adapter_linked   true
midi_68k_hardware_adapter_called   false
midi_68k_reset_vectors_changed     false
midi_sound_ram_writes              false
midi_scsp_mmio                     false
midi_smpc_commands                 false
midi_mc68ec000_execution           false
```

The adapter source contains real Saturn MMIO instructions, but linked code is
not executed merely because it exists in the image.

## Gate command

After the repository source suite is green, run against the accepted Stage-6B
Gate-5 project and a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_hardware_adapter_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-HARDWARE-ADAPTER-INERT-FULL-GATE1"
```

Expected state before the normal build transcript:

```text
Producer linked       : YES
Producer called       : NO
68K image linked      : YES
68K installed         : NO
Installer linked      : YES
Installer called      : NO
Runtime linked        : YES
Runtime called        : NO
Hardware adapter      : YES
Adapter linked        : YES
Adapter called        : NO
68K executed          : NO
Bridge active         : NO
```

The final result must be `SUCCESS`, with all normal compiler, startup assembly,
mixed-format link, ISO, packaged-PCM verification, and MODE1/2352 packaging
commands returning zero.

## Safety boundary

This gate does **not**:

- call the adapter;
- call the runtime orchestrator;
- issue `SNDOFF` or `SNDON`;
- write Sound RAM at runtime;
- change the MC68EC000 reset vectors;
- execute the MC68EC000;
- touch SCSP registers;
- write SAROO/card media.

No R18 deployment is authorized by this gate.

## Next gate

Only after this full-build gate passes may SRK define the first bounded physical
silent protocol proof. That later path may call:

```text
srk_saturn_midi_68k_protocol_begin(
    srk_saturn_midi_68k_hardware_adapter_ops()
)
```

and then poll non-blockingly.

The first physical success criteria remain:

```text
SNDOFF succeeds
68K install verifies
preload verifies
SNDON succeeds
READ_INDEX == 1
READ_SEQUENCE == 1
LAST_ERROR == 0
```

No MIDI-driven SCSP note is attempted until that handshake is proven on real
hardware.
