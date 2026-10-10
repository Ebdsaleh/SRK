# Saturn Audio — Silent MIDI MC68EC000 Physical Proof

## Purpose

This tranche defines the bounded one-shot controller for SRK's first real
Saturn MC68EC000 MIDI protocol execution proof.

It does **not** yet bind that controller to a diagnostic menu or controller
button.  No production path calls it in this tranche.

The purpose is to close the final control layer between the already-accepted:

- adapter-neutral MIDI/68K runtime;
- real Saturn SMPC/Sound-RAM hardware adapter;
- bounded 68K installer;
- deterministic SH-2 preload producer;
- protocol-only MC68EC000 consumer.

## Architecture

When a later physical candidate explicitly calls the controller, the path is:

```text
physical-proof begin
-> hardware-adapter operation table
-> safe SMPC command window
-> SNDOFF
-> install + exact read-back verify
-> deterministic preload publish + exact verify
-> SNDON
-> RUNNING
```

Subsequent frames use one non-blocking poll:

```text
physical-proof poll
-> flags
-> read sequence
-> read index
-> last error
```

There is no busy-wait loop in the proof controller.

## One-shot safety rule

`srk_saturn_midi_68k_physical_proof_begin()` is bounded to one begin attempt
until the caller explicitly resets the state.

This prevents a held/repeated input from repeatedly issuing the full:

```text
SNDOFF -> install -> preload -> SNDON
```

sequence.

If begin returns a failure status, later begin calls are inert until reset.

## Runtime status

The controller preserves the existing runtime status values:

```text
0  NOT_STARTED
1  SOUND_STOP_FAILED
2  INSTALL_FAILED
3  PRELOAD_FAILED
4  SOUND_START_FAILED
5  RUNNING
6  ACKNOWLEDGED
7  CONSUMER_ERROR
```

The controller also records:

```text
attempted
runtime_status
poll_count
flags
read_sequence
read_index
last_error
```

## Silent acknowledgement boundary

The physical proof is accepted only when the MC68EC000 consumer produces:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     1
LAST_ERROR     0
```

This proves the real hardware round trip:

```text
SH-2
-> Sound RAM preload/mailbox
-> installed MC68EC000 program
-> MC68EC000 execution
-> mailbox acknowledgement
-> SH-2 observation
```

## What this proof does not do

The protocol-only MC68EC000 consumer still does not:

- key on an SCSP slot;
- synthesize a MIDI note;
- consume the complete sequence;
- perform MIDI timing;
- implement program/bank changes;
- implement controllers;
- allocate voices;
- provide polyphony;
- use DSP effects.

Those belong to the next driver-expansion phase after physical protocol
acknowledgement is proven.

## Source-gate safety boundary

The committed proof controller contains calls that would reach real Saturn
hardware **if invoked**, but no production code invokes it in this tranche.

The controller itself contains no direct:

- SMPC address;
- Sound-RAM address;
- SCSP address;
- polling loop;
- controller/menu binding;
- SAROO/media write.

Therefore the source gate introduces no new runtime behavior.

## Gate order

Before any physical deployment:

1. source tests;
2. real legacy SH-ELF compiler gate for the proof controller;
3. complete fresh off-card full-build gate with the controller linked but
   uncalled;
4. explicit diagnostic control/telemetry binding;
5. another build/package gate;
6. guarded R18 deployment candidate;
7. physical silent acknowledgement test.

No MIDI-driven SCSP note is attempted before step 7 passes.

## Direction after acknowledgement

Once the silent physical round trip is accepted, SRK expands the resident
MC68EC000 implementation into the actual SRK-owned MIDI-file playback driver.
After that implementation is complete and physically characterized, SRK adds
Sega Saturn native Sound API compatibility as a separate compatibility layer.

> Safer is secure, secure is faster.
