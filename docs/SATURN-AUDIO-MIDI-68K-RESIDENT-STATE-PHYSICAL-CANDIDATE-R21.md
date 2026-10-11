# Saturn MIDI / MC68EC000 — R21 Full-State Physical Candidate

R21 is the Phase-B real-hardware candidate for SRK's dynamic resident MIDI state engine.

R20 physically accepted the content-independent runtime queue loop.  R21 moves the hardware boundary forward from record validation to **complete MIDI state mutation** while remaining silent.

## Baseline

R21 derives only from the accepted Phase-B inert full-build tree, which itself derives from the physically accepted R20 candidate.

The Phase-B image is compiler accepted and remains pinned at:

```text
program address : 0x00004000
stack           : 0x0007FFF0
word count      : 4898
byte size       : 9796
program end     : 0x00006644
runtime records : 1..32
SHA-256         : 39d5c1116affa95e2be7d5f94342e0ba70bfebf845b6f2cce292946894bd5bb9
```

Compiler evidence:

```text
source : 0edb77a5be40b6324166d72d53ae7ebcf9ce79ba3799b2d3cc8055aa11ead016
header : 01ce4a0e477830887feb7a92d41e1e1caefedacc6fed87bfa0805d9aeb7ff589
object : 6ce6a594361fbad251ae491538a181c108b1a76ddd185e3e3924e5b354d199d7
```

## R21 proof program

R21 uses 20 runtime records across channels 3 and 9.  The batch exercises all seven SRKM v1 opcodes and deliberately produces non-default state:

```text
1000   CC ch3 0=5
2000   CC ch3 32=9
3000   CC ch3 7=91
4000   CC ch3 10=73
5000   CC ch3 11=101
6000   CC ch3 64=127
7000   CC ch3 74=66
8000   PROGRAM ch3 12
9000   CHANNEL_PRESSURE ch3 70
10000  PITCH_BEND ch3 52,78
11000  NOTE_ON ch3 64,100
12000  NOTE_ON ch3 69,88
13000  POLY_AFTERTOUCH ch3 64,55
14000  NOTE_OFF ch3 64,32
15000  NOTE_ON ch3 69,0
16000  NOTE_ON ch3 64,77
17000  PROGRAM ch9 33
18000  CC ch9 7=84
19000  NOTE_ON ch9 48,96
20000  PITCH_BEND ch9 0,32
```

## Complete state verification

A public ACK is not enough for R21.

After the MC68EC000 completes the batch, the SH-2 verifier compares the complete model-derived state:

```text
256 channel-summary words
1024 controller words (2048 bytes)
128 active-note words (256 bytes)
```

The verifier returns one of:

```text
0 NOT_RUN
1 PASS
2 SUMMARY_MISMATCH
3 CONTROLLER_MISMATCH
4 ACTIVE_NOTE_MISMATCH
```

A mismatch records its first index, expected word and actual word.  `ACKNOWLEDGED` is only returned after the mailbox, resident-state telemetry, and complete state comparison all pass.

## Human-readable state

The physical screen additionally exposes representative post-execution state.

Channel 3:

```text
program             12
bank MSB / LSB      5 / 9
volume              91
pan                 73
expression          101
sustain             1
channel pressure    70
pitch bend          10036
last note/velocity  64 / 77
poly note/pressure  64 / 55
active notes        1
CC74                66
```

Channel 9:

```text
program             33
volume              84
pitch bend          4096
last note/velocity  48 / 96
active notes        1
```

The standalone host provides 28 text rows (`0..27`).  The state table ends at row 24, PASS is row 25, the A prompt is row 26, and START is row 27.

## Candidate safety boundary

R21 reuses the physically accepted R20 SMPC/Sound-CPU hardware adapter.  No second SNDOFF/SNDON implementation is introduced.

Build-time policy:

```text
state decoder linked                    YES
state decoder installed during build    NO
state decoder executed during build     NO
state candidate bound                    YES
MIDI-driven SCSP note                    NO
build-time SMPC commands                 NO
build-time Sound-RAM writes              NO
build-time MC68EC000 execution           NO
SAROO writes                             NONE
```

The candidate remains silent.

## Independent pre-media gate

The R21 source tranche also includes an independent read-only pre-media gate.  It re-opens a completed candidate and verifies:

- standalone manifest and successful report binding;
- full generated-file inventory;
- exact Phase-B image/compiler provenance;
- all ten generated candidate seams against current renderers;
- exact 20-record proof program;
- exact model-derived state snapshot;
- 256/1024/128 complete-state verification geometry;
- candidate main/menu/runtime hashes;
- release-A then fresh-A interlock;
- non-overlapping state/prompt screen rows;
- exact externally accepted BIN/CUE hashes;
- fresh MODE1 SAROO destination using only the read-only planner.

It has no apply path and performs no card writes.

## Whole-card guard

The same source tranche includes the R21 two-phase whole-card guard.

PREPARE:

```text
rerun independent R21 pre-media
-> create fresh whole-card inventory OFF CARD
-> immediately verify exact mounted-card match
-> zero card writes
```

APPLY requires the exact PREPARE manifest SHA-256 plus:

```text
DEPLOY-R21-RESIDENT-STATE-PROOF
```

Only the fresh R21 directory plus its accepted BIN/CUE may differ after deployment.  Conservative rollback refuses deletion if unexpected files or changed hashes appear.

## Physical PASS meaning

A real-Saturn R21 PASS means:

```text
SH-2 publishes richer 20-record SRKM batch
-> accepted hardware adapter stops sound CPU
-> exact Phase-B image installed
-> MC68EC000 validates complete batch atomically
-> MC68EC000 dynamically mutates MIDI state
-> full 256/1024/128 state surface matches host model
-> SH-2 exposes representative state on-screen
-> mailbox + RS telemetry + state verifier all PASS
```

Still excluded:

```text
multi-batch/refill streaming
timestamp scheduling
voice allocation
SCSP slot programming
MIDI-generated audio
polyphony
```

After R21 physical acceptance, the next substantial milestone is **multi-batch/refill service + timestamp scheduler** as one capability tranche.
