# Saturn Audio MIDI Mailbox Full-Build Gate

This gate proves that SRK can carry both the deterministic generated MIDI data
and the SH-2 preload producer through the complete known-good standalone Saturn
build pipeline while keeping that producer **uncalled**.

It is intentionally still off-card and behaviorally inert.

## Inputs already accepted before this gate

The sequence leading here is:

```text
SMF parser
  -> deterministic scheduler
  -> SRKM v1 records
  -> generated C event/tone data
  -> real legacy SH-ELF compile proof
  -> complete inert full-build proof
  -> SH-2 preload producer source contract
  -> real legacy SH-ELF preload-producer compile proof
  -> this gate
```

The preload producer owns only the reviewed Sound-RAM regions:

```text
0x00001000-0x000010FF  mailbox
0x00001100-0x000011FF  bounded 32-record queue
0x00003000-0x0000317F  three-tone diagnostic PCM bank
```

## Gate behavior

The gate starts from one already-successful standalone project and never edits
that baseline.

It first derives the already-proven inert MIDI-data gate, then copies:

```text
srk_saturn_midi_mailbox.c
srk_saturn_midi_mailbox.h
```

into the fresh project and appends the mailbox C translation unit to the copied
runtime translation unit solely for this proof.

The unchanged normal Python-native standalone builder then performs the complete
compile / startup-assembly / mixed-format link / ISO / packaged-PCM verification
/ MODE1-2352 packaging flow.

## Safety boundary

The preload producer is **linked but never called**.

Therefore this gate records:

```text
midi_bridge_active             false
midi_mailbox_producer_linked   true
midi_mailbox_producer_called   false
midi_sound_ram_writes          false
midi_scsp_mmio                 false
midi_smpc_commands             false
midi_mc68ec000_execution       false
```

The C file contains Sound-RAM write code, but code presence is not runtime
execution. No menu action or host callback reaches the producer in this gate.

No SAROO/card write is performed.

## Why the gate still derives from Stage 6B Gate 5

The accepted Gate 5 project remains the clean known-good standalone baseline.
Each experimental audio tranche is re-derived from that baseline instead of
chaining mutable build trees together.

This keeps provenance simple and makes regressions attributable to the current
addition only.

## Source gate

The new Python preparation code and CLI must pass the full SRK source suite
before the real off-card build is attempted.

Expected source-test total for this tranche:

```text
468 tests
```

## Real off-card build command

After the source gate is green:

```bat
python -m rikai_kotoba.tools.saturn_midi_mailbox_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-MAILBOX-INERT-FULL-GATE1"
```

The destination must not already exist.

Expected final status:

```text
Producer linked    : YES
Producer called    : NO
Bridge active      : NO
Result             : SUCCESS
```

Every normal build command must return zero.

## What success means

Success proves:

- deterministic MIDI event/tone data survives the complete Saturn build;
- the real legacy SH-ELF backend accepts the producer;
- the producer also survives the final mixed-format standalone link;
- the full ISO and MODE1/2352 packaging path still closes;
- existing Stage 6 packaged-PCM verification still closes;
- none of this required executing the new producer.

## Next boundary

Only after this gate is accepted should SRK begin the MC68EC000 consumer design.

The first consumer tranche should remain equally narrow:

1. define the 68K program image and reviewed Sound-RAM address;
2. parse/validate only the published mailbox header and first queue record;
3. acknowledge without touching SCSP slots;
4. compile and link it off-card;
5. only later let the 68K consumer drive one deterministic slot/note.

This keeps protocol proof separate from audible playback proof.

No R18 card deployment is authorized by this gate.

> Safer is secure, secure is faster. <3
