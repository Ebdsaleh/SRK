# Saturn Audio — Silent MIDI 68K Hardware Adapter

## Purpose

This tranche binds the already-reviewed adapter-neutral MIDI/MC68EC000 runtime
to the Saturn hardware operations that were physically accepted by the existing
standalone Audio diagnostic.

It does **not** activate the path.

Production does not call `srk_saturn_midi_68k_protocol_begin()` or
`srk_saturn_midi_68k_protocol_poll()` with this adapter yet. Merely compiling or
linking these files therefore does not stop/start the sound CPU, write Sound
RAM, install the 68K program, or launch the MC68EC000.

## Accepted hardware anchors

The adapter is intentionally constrained to the existing Audio constants:

```text
SMPC COMREG     0x2010001F
SMPC SF         0x20100063
VDP2 TVSTAT     0x25F80004
Sound RAM       0x25A00000
SNDON           0x06
SNDOFF          0x07
SMPC timeout    1000000
```

No SCSP register aperture is present in the adapter.

## SMPC command behavior

The stop operation reproduces the already accepted standalone Audio sequence:

```text
wait from V-BLANK-IN to V-BLANK-OUT
wait until SF bit 0 is clear
SF = 1
COMREG = SNDOFF
wait until SF bit 0 is clear
```

The start operation uses the same Type-B command helper with `SNDON`, matching
the accepted Stage 1-6 initialization flow.

No new SMPC command protocol is introduced here.

## Runtime operation table

The adapter supplies the six operations required by
`SRK_SATURN_MIDI_68K_RUNTIME_OPS`:

```text
stop_sound_cpu
install_program
publish_preload
verify_preload
start_sound_cpu
read_mailbox_word
```

Bindings are:

```text
stop_sound_cpu   -> accepted SMPC SNDOFF flow
install_program  -> srk_saturn_midi_68k_install_while_stopped
publish_preload  -> srk_saturn_midi_preload_publish
verify_preload   -> exact Sound-RAM read-back verification
start_sound_cpu  -> accepted SMPC SNDON flow
read_mailbox_word-> bounded Sound-RAM mailbox read
```

## Exact preload verification

`verify_preload` first requires `srk_saturn_midi_preload_is_ready()` and then
checks the runtime-sensitive mailbox fields:

```text
WRITE_SEQUENCE == 1
READ_SEQUENCE  == 0
WRITE_INDEX    == SRK_MIDI_EVENT_COUNT
READ_INDEX     == 0
LAST_ERROR     == 0
```

It then reads back every word of all three deterministic tone-bank waveforms
and every four-word serialized SRKM queue record.

This means `SNDON` is not requested by the adapter-neutral orchestrator unless
the complete program preload has been verified.

## Deliberate exclusions

This source tranche does not:

- call the runtime orchestrator;
- install the MC68EC000 program at runtime;
- change reset SSP/PC at runtime;
- publish the MIDI preload at runtime;
- execute the MC68EC000;
- access SCSP registers;
- produce an audible MIDI note;
- bind a controller/menu action;
- write SAROO or any SD-card file.

The C adapter is an inert operation-table provider until another production
control path explicitly passes it to the runtime.

## Gate order

The required evidence order is:

1. source tests;
2. real legacy SH-ELF compile probe for the adapter C source;
3. complete fresh off-card standalone full-build with the adapter linked but
   uncalled;
4. only then design the bounded physical protocol-proof control path.

No R18 deployment is authorized by this document.

## Physical proof target after all off-card gates

The first real execution proof remains deliberately silent. Success is:

```text
SNDOFF succeeds
68K program installs and verifies
preload publishes and verifies
SNDON succeeds
68K sees READY and validates first SRKM record
READ_INDEX becomes 1
READ_SEQUENCE becomes 1
LAST_ERROR remains 0
```

Only after that hardware proof is accepted should SRK attempt an audible
MIDI-driven SCSP note.
