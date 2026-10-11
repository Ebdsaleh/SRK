# Saturn Audio — General Silent MIDI MC68EC000 Resident Decoder

## Status

R19 physically accepted the complete canonical 27-record SRKM v1 batch on the
real Saturn MC68EC000.

That accepted image was intentionally unrolled: every queue word and every
final state word was known at image-generation time.  This document defines the
first post-R19 gate that removes that content dependency.

The new decoder remains completely silent.

## Purpose

Phase A asks one narrow question:

> Can one fixed resident MC68000 program walk and validate an arbitrary bounded
> SRKM v1 queue using runtime loop control and pointer addressing, without
> embedding or knowing the records in advance?

This is the instruction/addressing risk that R19 deliberately did not combine
with the first full-batch hardware proof.

## Runtime contract

The decoder waits for `READY`, then validates:

```text
mailbox magic 0
mailbox magic 1
mailbox version
queue capacity = 32
write sequence != 0
1 <= queue count <= 32
write index == queue count
```

It then reloads the runtime queue count and traverses the queue from `0x1100`
with an address-register post-increment loop.

Each SRKM v1 record remains four big-endian Sound-RAM words:

```text
word 0  timestamp high
word 1  timestamp low
word 2  opcode high byte / channel low byte
word 3  data0 high byte / data1 low byte
```

For every record the resident image validates:

```text
opcode  = 1..7, exactly one defined SRKM v1 opcode
channel = 0..15
data0    = 0..127
data1    = 0..127
```

The program therefore depends on the SRKM v1 *contract*, not on the canonical
27-record payload.

## New machine-code mechanisms under review

R19 had already physically exercised absolute-short loads/stores, immediate
comparisons/masks and word branches.

Phase A deliberately adds only the mechanisms needed for a general bounded
loop:

```text
LEA (xxx).W,A0
MOVE.W (A0)+,Dn
MOVE.W Dn,Dm
CMP.W Dn,Dm
MOVE.W #imm,Dn
ADDQ.W #1,Dn
SUBQ.W #1,Dn
BHI.W
```

The source regression suite executes the actual generated machine words with an
independent reviewed-subset interpreter.  It checks the pointer read addresses,
branch behavior, runtime count and failure paths rather than merely inspecting
Python model output.

## Dynamic telemetry

The decoder reuses the established telemetry page at `0x1D00` but publishes a
new identity:

```text
magic       0x5244  "RD"
version     1
processed   runtime accepted-record count
current     current/next runtime record index
final hi    high word of the most recently accepted timestamp
final lo    low word of the most recently accepted timestamp
ready       1 only after the entire runtime batch validates
```

The public mailbox acknowledgement is written only after decoder `ready = 1`.
Success is therefore:

```text
READ_INDEX    = actual queue count
READ_SEQUENCE = current non-zero WRITE_SEQUENCE
LAST_ERROR    = 0
```

The decoder is not hard-coded to `27` or to write sequence `1`.

## Failure behavior

The existing reviewed error-number family is retained:

```text
1  magic
2  version
3  contract
4  empty queue
6  count/index
7  record field
```

Every terminal failure explicitly withdraws:

```text
READ_SEQUENCE = 0
READ_INDEX    = 0
decoder ready = 0
```

before publishing `LAST_ERROR`.

No partial public acknowledgement is possible.

## Explicitly unchanged state boundary

Phase A does **not** write the post-queue command-state region:

```text
0x1200-0x13FF  channel summaries
0x1400-0x1BFF  controller matrix
0x1C00-0x1CFF  active-note bitmaps
```

The only runtime writes are mailbox acknowledgement/error words and the
`0x1D00` telemetry page.

This is deliberate.  It separates runtime queue traversal from the next risk:
dynamic per-opcode state addressing and mutation.

## Source-gate regression coverage

The regression suite proves:

1. the machine image is deterministic and content-independent;
2. the existing canonical 27-record program is consumed through the runtime
   loop rather than an unrolled table;
3. both a one-record batch and a full 32-record batch acknowledge their actual
   runtime counts;
4. invalid channel, opcode or 7-bit data fields fail without acknowledgement;
5. empty, oversized, count/index-mismatched and zero-sequence mailboxes fail;
6. a 32-record run reads exactly the 128 queue words from `0x1100` through
   `0x11FE` in order via the runtime pointer;
7. no command-state or Audio/SCSP-owned region is written;
8. the generated C representation is deterministic, inert and contains no
   SCSP/SMPC/Sound-RAM host access.

## Safety boundary

This tranche only generates a constant MC68000 word image and tests it on the
host.

```text
Saturn hardware action       NO
SMPC command                 NO
Sound-RAM runtime write      NO
MC68EC000 execution          NO
SCSP register write          NO
MIDI-driven SCSP note        NO
SAROO/card write             NO
R17/R18/R19 modification     NO
```

No normal standalone diagnostic code installs or invokes this new decoder.

## What Phase A does not yet prove

This gate must not be described as complete MIDI playback.  It does not yet
implement:

- dynamic channel-summary mutation;
- the 128-controller matrix update path;
- active-note bitmap mutation;
- queue refill or multi-batch streaming;
- sequence rollover/continuous resident service;
- timestamp scheduling;
- voice allocation;
- SCSP slot programming;
- MIDI-driven audio.

## Planned progression

After this source gate is accepted:

```text
Phase A  dynamic bounded decoder loop          <- this gate
Phase B  dynamic silent state mutation
Phase C  resident multi-batch/refill service
Phase D  timestamp scheduler
Phase E  voice allocator + deterministic tone
Phase F  first MIDI-driven SCSP note
Phase G  Melody Town Theme single-instrument playback
Phase H  Double Impact compatibility corpus
```

Each stage retains the same rule used to reach R19: isolate one new hardware
risk, prove it, and preserve the previous physical baseline.

> Safer is secure, secure is faster.
