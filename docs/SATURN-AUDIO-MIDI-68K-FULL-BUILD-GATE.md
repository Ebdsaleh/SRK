# Saturn Audio MIDI MC68EC000 Full-Build Gate

This gate proves that SRK's complete pre-runtime MIDI stack survives the normal
Saturn standalone build before any MC68EC000 installation or execution is
introduced.

It is deliberately off-card and behaviorally inert.

## Inputs

The fresh gate tree contains all three currently accepted layers:

```text
SRK generated MIDI event/tone data
+
SH-2 mailbox preload producer
+
protocol-only MC68EC000 program image
```

The MC68EC000 image is still represented only as constant C data.

## Baseline

The gate always derives again from the accepted Stage-6B standalone baseline.
It does not mutate that baseline and does not derive from a mutable experimental
output tree.

The derivation sequence is:

```text
accepted Stage-6B project
  -> inert generated-MIDI bridge gate
  -> uncalled SH-2 mailbox-producer gate
  -> uninstalled protocol-only 68K image gate
  -> normal Python-native standalone builder
```

## 68K image contract

The constant program remains pinned to:

```text
program address  0x00000600
stack address    0x0007FFF0
program size     162 bytes
program words    81
```

The program validates mailbox metadata and the canonical first SRKM event,
acknowledges one record, and then holds. It contains no SCSP playback logic.

## Gate-only build integration

For this proof, the fresh derived project receives:

```text
src/srk_saturn_midi_68k_program.c
src/srk_saturn_midi_68k_program.h
```

The constant program source is appended to the copied
`src/srk_saturn_runtime.c` translation unit only inside the fresh gate tree.
This allows the unchanged normal standalone build driver to compile and link
the representation without promoting it into the production standalone source
lists yet.

The fresh manifest is regenerated after every injection and pins the hashes of
all generated inputs.

## Safety state

The manifest must record:

```text
midi_bridge_active             false
midi_mailbox_producer_linked   true
midi_mailbox_producer_called   false
midi_68k_program_linked        true
midi_68k_program_installed     false
midi_68k_reset_vectors_changed false
midi_sound_ram_writes          false
midi_scsp_mmio                 false
midi_smpc_commands             false
midi_mc68ec000_execution       false
```

Therefore a successful build proves link/package compatibility only.

It does **not** prove runtime execution.

## Required build proof

The normal Python-native standalone build must complete all existing steps:

- compile all standalone C translation units;
- assemble startup;
- mixed ELF/COFF Stage-6B link;
- ISO packaging;
- exact packaged-PCM verification;
- MODE1/2352 BIN/CUE packaging.

Every command must return zero.

The CLI success boundary is:

```text
Producer linked   : YES
Producer called   : NO
68K image linked  : YES
68K installed     : NO
68K executed      : NO
Bridge active     : NO
Result            : SUCCESS
```

## What this gate must never do

This tranche performs no:

- call to `srk_saturn_midi_preload_publish()`;
- Sound RAM runtime write;
- 68K program installation;
- reset SSP/PC modification;
- SMPC SNDON/SNDOFF command;
- MC68EC000 execution;
- SCSP MIDI playback;
- SAROO/card write.

The generated deployable image from this gate is evidence only and is not an
R18 deployment candidate.

## Next step after success

Only after this complete build gate passes should SRK add a bounded installer
contract that can prepare the silent protocol proof:

1. stop/hold the sound CPU using the already accepted SMPC sequencing;
2. install the 81 program words at Sound RAM `0x00000600`;
3. write reset SSP `0x0007FFF0`;
4. write reset PC `0x00000600`;
5. publish the deterministic MIDI mailbox/tone preload;
6. verify the installed words and mailbox from the SH-2 before any launch;
7. keep the launch itself behind a separate physical-validation tranche.

The first launched MC68EC000 proof remains silent: successful execution is
observed only through mailbox acknowledgement/error state. A MIDI-driven SCSP
note comes later, after the protocol path is physically proven.
