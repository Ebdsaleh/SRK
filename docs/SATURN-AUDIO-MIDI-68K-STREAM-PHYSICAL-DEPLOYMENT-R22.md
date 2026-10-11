# Saturn Audio / MIDI — R22 Stream Scheduler Guarded Media Boundary

R22 is the first real-hardware candidate for the resident multi-batch/refill and
timestamp scheduler milestone.  This document defines the independent media
boundary around that candidate.  It does not record physical acceptance.

## Accepted candidate build evidence

The external candidate build must remain pinned by the exact BIN/CUE hashes
provided to the pre-media and guarded-deployment tools.  The pre-media gate also
independently reconstructs and verifies the compiler-accepted resident image,
resident C representation, SH-2 producer representation, and the R22 physical
proof renderer.

## Independent pre-media requirements

The pre-media gate must prove, without writing the SAROO card:

- the candidate standalone manifest and successful build report match;
- every generated-file inventory entry still matches disk;
- resident image geometry remains 5123 words / 10246 bytes / `0x4000-0x6806`;
- accepted resident source/header/object compiler evidence matches;
- accepted producer source/header/object compiler evidence matches;
- the physical proof remains 40 records split 32+8, sequences 1 then 2;
- clock milestones remain 0, 15000, 32000, and 40000 microseconds;
- all seven SRKM v1 opcodes remain covered;
- final verification still covers 256 summary, 1024 controller, and 128 active-note words;
- candidate UI retains the release-A / fresh-A interlock;
- final visible state remains derived from the host stream model;
- deployable BIN/CUE hashes equal the externally accepted build output;
- the destination `SRK-Diagnostics-R22` is fresh;
- card writes are zero.

## Two-phase whole-card guard

PREPARE:

1. re-runs the independent R22 pre-media gate;
2. creates a complete SAROO-card inventory outside the card;
3. immediately verifies that inventory exactly;
4. writes nothing to the card.

APPLY requires:

- the exact reviewed PREPARE manifest SHA-256;
- confirmation token `DEPLOY-R22-STREAM-SCHEDULER-PROOF`;
- another successful pre-media gate;
- an exact whole-card match immediately before the write.

Only these differences are authorized after a successful APPLY:

```text
saroo/ISO/TEST/SRK-Diagnostics-R22
saroo/ISO/TEST/SRK-Diagnostics-R22/SRK-Diagnostics.bin
saroo/ISO/TEST/SRK-Diagnostics-R22/SRK-Diagnostics.cue
```

Any other card difference fails the post-write guard.  Rollback is deliberately
conservative: the new R22 directory is automatically removed only when it
contains exactly the just-written BIN/CUE with the expected hashes.  After a
rollback the original whole-card baseline must verify again.

## Physical acceptance contract after guarded deployment

R22 can be accepted only from the first terminal result of a real Saturn run.
PASS must visibly prove:

```text
clock 0 us      -> 0 records, no ACK
clock 15000 us  -> exactly 15 records, no ACK
clock 32000 us  -> 32 records, sequence 1 ACK
refill at 32000 -> zero batch-2 records execute early, sequence 1 retained
clock 40000 us  -> 40 total records, sequence 2 ACK
```

and complete persistent MIDI state must match the host model across:

```text
256 channel-summary words
1024 controller words
128 active-note words
```

The candidate remains silent.  No MIDI-driven SCSP note is enabled in R22.
