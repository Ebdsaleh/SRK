# Saturn MIDI / MC68EC000 multi-batch refill + timestamp scheduler milestone

## Baseline

R21 is the immutable real-hardware baseline for complete dynamic MIDI state mutation.

R21 physically proved:

```text
all seven SRKM v1 opcodes
+ persistent 16-channel summaries
+ complete 16x128 controller matrix
+ complete 16x128 active-note bitmap
+ 1408-word SH-2 full-state verification
```

The accepted state image remains unchanged. This milestone introduces a new resident image and service contract.

## Capability goal

Treat refill streaming and timestamp scheduling as one capability milestone:

```text
one persistent resident MC68EC000 service
-> state initialized once
-> accept batch sequence 1
-> validate complete batch
-> wait until each record timestamp becomes due
-> mutate persistent MIDI state
-> ACK only after whole batch executes
-> producer refills the same 32-record queue as sequence 2
-> preserve state across the refill
-> continue indefinitely
```

This milestone remains silent: no MIDI-driven SCSP note is attempted.

## Sound-RAM ownership

Existing accepted layout remains:

```text
0x1000-0x10FF  mailbox
0x1100-0x11FF  32-record SRKM queue
0x1200-0x13FF  channel summaries
0x1400-0x1BFF  controller matrix
0x1C00-0x1CFF  active-note bitmap
0x1D00-0x1DFF  R21/RS state telemetry
0x1E00-0x1FFF  NEW stream/scheduler service block
0x2000         accepted Audio/SCSP ownership boundary
```

The new service block ends exactly at `0x2000` and cannot overlap accepted Audio/SCSP RAM.

## Refill protocol

The existing queue remains bounded at 32 records. Longer programs are split into consecutive batches:

```text
records 0..31   -> sequence 1
records 32..63  -> sequence 2
records 64..95  -> sequence 3
...
```

Sequences are strict non-zero 16-bit values:

```text
1, 2, 3, ... FFFE, FFFF, 1, 2, ...
```

A resident service must never execute the same published sequence twice.

A batch is not acknowledged until every record in that batch has reached its due time and mutated state.

The producer must not refill the shared queue until the previous sequence has been acknowledged.

## Atomic batch validation

Every refill is validated completely before its first state mutation.

Validation covers:

```text
mailbox magic/version
queue capacity
record count 1..32
write-index/count agreement
strict sequence continuity
valid SRKM v1 opcode
channel 0..15
data bytes 0..127
chronological timestamps
cross-batch timestamp continuity
```

A malformed refill therefore cannot partially mutate MIDI state.

## Persistent state

Unlike the one-batch Phase-B image, the stream service initializes MIDI state once at service boot.

It does **not** reset the state arrays at each refill.

The following therefore survive sequence transitions:

```text
program/bank
all controller values
volume/pan/expression/sustain
channel pressure
pitch bend
active-note bitmap/count
last note/velocity
poly-aftertouch state
event count
last opcode
```

## Timestamp scheduler

Each SRKM record retains its absolute 32-bit `time_us` timestamp.

The resident MC68EC000 reads a producer-published 32-bit microsecond clock and applies a record only when:

```text
published_now_us >= record.time_us
```

If the record is still early, the service remains in `WAIT_TIME` and the batch remains unacknowledged.

### Clock publication safety

The Saturn sound CPU is 16-bit, while the clock is 32-bit. The producer therefore publishes the clock with an odd/even generation seqlock:

```text
write generation = odd
write clock high
write clock low
write generation = even
```

The resident 68K reads:

```text
generation A
clock high
clock low
generation B
```

and retries unless:

```text
generation A == generation B
and generation is even
```

This prevents torn 32-bit time samples without requiring an atomic 32-bit Sound-RAM transaction.

### Current timebase scope

This milestone proves the scheduler against a **producer-published microsecond clock**.

It does not yet claim that the final hardware time source has been selected or physically accepted. A later integration can feed the same reviewed clock publication contract from the chosen Saturn hardware-derived time source without changing resident scheduling semantics.

## Service telemetry

The service block begins at `0x1E00` and contains:

```text
magic/version
RUNNING / WAIT_BATCH / WAIT_TIME / ERROR flags
acknowledged batch count
32-bit total processed records
current sequence/index
last executed timestamp
next due timestamp
producer clock generation/high/low
last service error
stable-read scratch words
```

The public mailbox remains the authoritative producer/consumer sequence boundary.

## Exact-machine regression

The generated MC68000 words are executed in the reviewed instruction-level model across a real refill boundary:

```text
batch 1: 32 records
clock 0      -> no records executed
clock 15000  -> 15 records executed, no ACK
clock 32000  -> batch 1 complete, ACK sequence 1

batch 2: 8 records
clock 32000  -> no premature batch-2 execution
clock 40000  -> batch 2 complete, ACK sequence 2
```

The resulting complete MIDI state is compared to the host stream model.

Negative exact-machine paths include:

```text
wrong refill sequence -> fail-stop before mutation
cross-batch timestamp regression -> fail-stop before mutation
```

All generated Sound-RAM writes remain below `0x2000`.

## Legacy compiler gate

The legacy gate compiles two independent generated representations with the production SH-ELF policy:

```text
resident MC68EC000 stream-service constant image
SH-2 refill/timebase producer helper
```

Compiler flags remain:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The compile gate performs no link, ISO build, card write, Sound-RAM write, SMPC command or MC68EC000 execution.

## Inert standalone integration

After real compiler evidence is accepted, a fresh standalone tree is derived from the physically accepted R21 candidate.

Required inert boundary:

```text
Existing R21 binding         : PRESERVED
Resident stream linked       : YES
Resident stream installed    : NO
Resident stream executed     : NO
SH-2 stream producer linked  : YES
SH-2 stream producer invoked : NO
New candidate bound          : NO
MIDI-driven SCSP note        : NO
Build-time hardware I/O      : NO
SAROO writes                 : NONE
```

The inert image must not be deployed.

## Next physical milestone

After source/model + legacy compiler + inert full-build acceptance, build one real-Saturn candidate that visibly proves both parts together:

```text
at least two queue refills
+ at least one timestamp wait before due time
+ no premature state mutation
+ sequence 1 ACK
+ queue refill
+ sequence 2 ACK
+ persistent state spanning both batches
```

The physical proof should expose service telemetry and selected state values, not just a generic ACK.

## After physical stream/scheduler acceptance

The next larger capability milestone is:

```text
voice allocator
+ SCSP slot-state model
+ first MIDI-driven SCSP note
```

Then the first musical target is the CC0 Melody Town Theme, followed by the Double Impact MIDI corpus.

R17 / R18 / R19 / R20 / R21 remain immutable historical hardware anchors.
