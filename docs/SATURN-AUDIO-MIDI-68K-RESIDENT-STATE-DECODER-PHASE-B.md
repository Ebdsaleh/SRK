# Saturn Audio / MIDI — Phase B resident MC68EC000 state decoder

## Purpose

R20 physically accepted the content-independent runtime SRKM queue loop on the real Saturn MC68EC000. Phase B advances that accepted architecture from **validation-only decoding** to **dynamic MIDI command-state mutation** while remaining silent.

This milestone is intentionally larger than the preceding proof seams. It contains the complete host-reviewed state engine, machine-word/model equivalence tests, the legacy compiler gate and the inert standalone full-build integration gate.

R17, R18, R19 and R20 remain immutable historical hardware anchors.

## Phase B capability

The new image consumes any valid `1..32` record SRKM v1 batch and dynamically maintains:

- all sixteen channel summary blocks;
- all `16 x 128 = 2048` controller bytes;
- all `16 x 128` logical active-note bits;
- program change;
- bank MSB / bank LSB;
- volume, pan and expression;
- sustain state;
- channel pressure;
- polyphonic aftertouch summary;
- 14-bit pitch bend;
- note on / note off state and active-note counts;
- event count and last-opcode telemetry.

It does **not** program SCSP slots or generate audio.

## Atomic two-pass contract

Phase B deliberately does not mutate live MIDI state while it is still discovering whether a batch is valid.

```text
READY
-> validate mailbox
-> PASS 1: validate every runtime record
-> only after complete validation: initialize deterministic state
-> PASS 2: dynamically apply every record
-> publish state-ready telemetry
-> acknowledge actual runtime record count
```

A malformed runtime record therefore fails before the channel/controller/note state region is modified.

## Sound-RAM state ownership

The already-reviewed state layout remains:

```text
0x1200-0x13FF  channel summaries
0x1400-0x1BFF  controller matrix
0x1C00-0x1CFF  active-note bitmap
0x1D00-0x1DFF  telemetry
0x2000          accepted Audio/SCSP ownership boundary
```

Phase B writes only below `0x2000`.

## Opcode semantics

### NOTE_OFF

- records last note / release velocity;
- clears the logical active-note bit;
- decrements active-note count only when the note was previously active.

### NOTE_ON

- records last note / velocity;
- non-zero velocity sets the logical active-note bit;
- increments active-note count only when the note was previously inactive;
- velocity zero performs note-off state behavior.

### POLY_AFTERTOUCH

Updates the last polyphonic-aftertouch note and pressure.

### CONTROL_CHANGE

Every controller number `0..127` updates the complete controller matrix.

The channel summary mirrors:

```text
CC 0   bank MSB
CC 32  bank LSB
CC 7   volume
CC 10  pan
CC 11  expression
CC 64  sustain (>=64 on, <64 off)
```

### PROGRAM_CHANGE

Updates the channel program.

### CHANNEL_PRESSURE

Updates channel pressure.

### PITCH_BEND

Builds the complete 14-bit value:

```text
(data1 << 7) | data0
```

## Generated image identity

Pinned source-gate image:

```text
Program address : 0x00004000
Stack           : 0x0007FFF0
Word count      : 4898
Byte size       : 9796
Program end     : 0x00006644
Runtime records : 1..32

SHA-256:
39d5c1116affa95e2be7d5f94342e0ba70bfebf845b6f2cce292946894bd5bb9
```

The larger image is expected: deterministic initial state for all channels/controllers/notes is emitted only after full queue validation, followed by the dynamic mutation engine.

## New MC68000 mechanisms

In addition to the R20 physically accepted loop subset, Phase B uses reviewed encodings for:

```text
MOVE.B (A0)+,Dn
MOVE.W d16(An),Dn
MOVE.W Dn,d16(An)
ADDA.W Dn,An
MOVE.B Dn,(An)
BSET Dn,(An)
BCLR Dn,(An)
ADD.W Dn,Dm
general ADDQ.W / SUBQ.W
BCS.W
```

These new mutation instructions are source/model tested now but are **not yet physically accepted** on Saturn hardware.

## Whole-state equivalence gate

The regression interpreter executes the exact generated machine words and compares the resulting Sound RAM against the established host-side command engine.

It compares:

```text
all 256 channel-summary words
all 2048 controller bytes
all 256 active-note bitmap bytes
mailbox completion
state telemetry
```

Coverage includes:

- canonical 27-record diagnostic program;
- all seven SRKM v1 opcode classes across channels;
- bank/volume/pan/expression/sustain plus arbitrary controller storage;
- duplicate note-on/note-off accounting;
- zero-velocity NOTE_ON;
- a complete 32-record runtime batch;
- invalid-record rejection before any state mutation.

## Legacy compiler gate

The generated Phase-B C representation is compiled off-card with the production legacy policy:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The compiler gate performs no link, ISO build, SAROO write, Sound-RAM access, SMPC command, SCSP access or MC68EC000 execution.

CLI:

```text
python -m rikai_kotoba.tools.saturn_midi_68k_resident_state_decoder_compile_probe
```

A real successful run must preserve the printed image/source/header/object hashes for the next gate.

## Inert standalone full-build gate

The full-build gate starts only from the exact physically accepted R20 candidate tree.

It requires external evidence for:

- accepted R20 manifest;
- accepted R20 build report;
- accepted R20 deployable BIN/CUE;
- exact Phase-B image;
- exact compiler-accepted Phase-B source/header/object hashes.

It copies verified R20 generated inputs to a fresh tree, preserves the R20 main/menu byte-for-byte and links the Phase-B state decoder as constant data in the standalone runtime translation unit.

Required boundary:

```text
Existing R20 binding    : PRESERVED
State decoder linked    : YES
State decoder installed : NO
State decoder executed  : NO
Candidate bound         : NO
Dynamic state mutation  : PRESENT IN LINKED IMAGE, NOT EXECUTED
MIDI-driven SCSP note   : NO
Build-time hardware I/O : NO
SAROO writes            : NONE
```

The inert full-build image must never be deployed.

## Explicit exclusions

Phase B does not yet implement:

```text
multi-batch / queue-refill service
wall-clock timestamp scheduling
voice allocation
SCSP slot programming
MIDI-generated audio
polyphony
```

## Next physical milestone

After source, legacy compiler and inert full-build acceptance, create one new physical candidate that proves **state results**, not merely mailbox acknowledgement.

The proof batch should cover all seven opcodes plus meaningful state transitions. The SH-2 proof UI should independently read and verify selected state words / controller values / note bits after MC68EC000 acknowledgement.

Only after that state-mutating image passes real Saturn hardware should work advance to a resident refill service and timestamp scheduler.
