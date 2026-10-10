# Saturn Audio MIDI Hardware Bridge — Prebuild Contract

This tranche establishes the first hardware-facing shape of SRK's MIDI playback
work without enabling any new Saturn hardware behavior yet.

The previous layers are already separated cleanly:

```text
SMF parser
    -> deterministic tempo/channel scheduler
    -> SRKM v1 normalized playback records
```

This tranche adds:

```text
SRKM v1
    -> bounded Sound RAM mailbox/queue layout
    -> SRK-owned deterministic tone bank
    -> generated C89 event/tone tables
```

The generated C is deliberately **not yet added to the standalone build list**.
That is the next gate. This keeps the Sound RAM ownership and SH-2/MC68EC000
contract reviewable before code begins touching live audio state.

## Sound RAM ownership

Saturn Sound RAM is treated as a 512 KiB address space. The proposed new regions
are:

```text
0x00001000-0x000010FF  SRK MIDI mailbox
0x00001100-0x000011FF  bounded 32-record event queue
0x00003000-0x0000317F  three x 64-sample PCM16 tone bank
```

These regions are validated not to overlap the already accepted standalone
Audio/SCSP ownership:

```text
0x00000000-0x00000401  68K vectors + current dummy loop
0x00002000-0x000020C9  Stage 1 tone
0x00002400-0x00002601  Stage 4 shaped PCM
0x00002800-0x00002C01  Stage 6 packaged PCM
```

The future real MC68EC000 program may use the space after the existing reset
stub and before the MIDI mailbox. Its exact code layout is intentionally not
chosen in this tranche.

## Mailbox words

The mailbox is word-oriented so both CPUs can consume an explicit layout rather
than sharing a compiler-dependent C struct.

```text
word  0  magic0          0x5352
word  1  magic1          0x4B4D
word  2  version         1
word  3  flags
word  4  write sequence
word  5  read sequence
word  6  write index
word  7  read index
word  8  queue capacity
word  9  queue count
word 10  last error
word 11  reserved
```

Producer/consumer ordering and the final command/acknowledgement protocol are
still deferred until the MC68EC000 program exists. The current contract only
reserves stable words and bounded storage.

## Queue

The queue has 32 records, enough to hold all 27 channel events in the canonical
SRK diagnostic sequence in one bounded fill.

Each record remains the already-defined 8-byte SRKM v1 event representation:

```text
BE32 absolute time_us
U8   opcode
U8   channel
U8   data0
U8   data1
```

## Deterministic tone bank

Programs 0, 1 and 2 will initially map to three small SRK-owned PCM16 waveforms:

```text
program 0  square
program 1  triangle
program 2  saw
```

Each waveform is 64 samples. They are diagnostic sources, not a General MIDI
instrument set. Their purpose is to make bank/program/note/pan/pitch sequencing
unambiguous on real hardware before any larger musical instrument system is
attempted.

## Generated source

The Python source of truth is:

```text
src/rikai_kotoba/hardware/saturn/midi_bridge.py
```

It renders the committed bridge files:

```text
integrations/saturn/standalone/srk_saturn_midi_generated.h
integrations/saturn/standalone/srk_saturn_midi_generated.c
```

Regression tests require the committed C files to match the Python renderer
exactly.

The C is C89-friendly and intentionally contains no `volatile` MMIO access, no
SCSP register writes, and no Sound RAM pointer dereferences. Therefore this
tranche cannot alter hardware behavior even if inspected or copied manually.

## Next gate

After the source gate passes:

1. copy the generated MIDI bridge files into fresh standalone project trees;
2. add them to Python-native compilation while leaving them behaviorally inert;
3. prove the legacy SH-ELF compiler accepts them;
4. define the MC68EC000 command consumer and SH-2 producer separately;
5. source/build gate that path;
6. only then consider a fresh R18 candidate and guarded SAROO deployment.

External physical MIDI input remains out of scope. The target is deterministic
MIDI file/sequence playback on standard Saturn hardware.
