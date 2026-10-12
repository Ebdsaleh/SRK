# Saturn Audio/MIDI — R24 Physical Acceptance

R24 is the first SRK milestone that physically plays a complete real Standard MIDI File through the Saturn SH-2 -> Sound RAM -> resident MC68EC000 -> SCSP path.

## Accepted physical result

The guarded R24 candidate was deployed only to the fresh SAROO destination:

```text
saroo/ISO/TEST/SRK-Diagnostics-R24
```

The real Saturn run reached the successful terminal boundary after consuming the complete CC0 `Melody Town Theme.mid` program once.

Observed final telemetry:

```text
Polls                 927
Flags                 0x0001
Read sequence         10
Read index            22
Last error            0
Phase                 4
Records               310
Batch count           10
Clock us              108347424
Clock source Hz       26874100
Producer sequence     10
Producer index        22
Published batches     10
Note On               140
Note Off              140
Active voices         0
Peak voices           2
Busy allocations      0
Polyphony seen        1
PAL                   0
Clock group B         0
State verify          1
Voice error           0

Song PASS: 310 events / peak voices 2
```

The user confirmed that the song played audibly and stopped at the terminal PASS screen. The complete event stream therefore did not loop indefinitely.

## Physical evidence

```text
Recording : SRK-DIAG(20261012-094057).mp4
Bytes     : 22794694
Duration  : 109.466667 seconds
Audio     : AAC stereo, 44100 Hz
SHA-256   : 3f870f47ff515f3a41cd012edff9bbe54dec475ac5a6a2870b5145b539a3ee52

Terminal image : SRK-DIAG_IMG(1).jpg
SHA-256        : ed8a0eb6be22c97e989eae103e20abbdc15b69b4347903fe91429243ebcbbee3
```

The source MIDI duration is 108151354 us. The terminal hardware clock reached 108347424 us, only 196070 us after the source end point; the recording duration also covers one complete performance plus the short pre/post capture margin.

## What R24 physically proves

R24 proves on real Saturn hardware that:

- an actual repository `.mid` file can be converted through SRK's generic MIDI pipeline;
- all 310 normalized records can be streamed through ten bounded queue batches;
- a real SH-2 FRT-derived monotonic clock can drive the playback timeline;
- runtime VDP2 clock-mode selection works for this console (`PAL=0`, group A, 26874100 Hz);
- 140 Note On and 140 Note Off events reach the resident MC68EC000 service;
- two simultaneous SCSP voices are observed without a BUSY allocation;
- the calibrated pitch-table path produces a recognisable melodic performance;
- all notes are released by the end of playback;
- the final 1408-word MIDI state comparison passes;
- the original FRT TCR restoration path reaches the successful terminal boundary;
- the song terminates normally instead of looping.

## Musical-fidelity qualification

R24 is accepted as a **real-SMF transport/timing/polyphony physical proof**, not as a final musical-synthesis fidelity proof.

The user reported that some notes sounded unusually short or abrupt. Two facts matter:

1. the source itself contains intentionally short notes, so a portion of the perceived staccato behavior is part of the MIDI sequence;
2. the R24 resident service performs a deliberately hard Note Off: after issuing SCSP KEY_OFF it immediately writes mixer level zero for the slot. R24 therefore does not allow the SCSP envelope generator to produce an audible release tail.

That hard mute was appropriate for deterministic first-song ownership and final-zero-voice proof, but it is audibly abrupt and must not be mistaken for final instrument behavior.

R24 also still uses the small deterministic diagnostic loop waveform rather than a General MIDI instrument/tone bank. Program Change is preserved as MIDI state, not rendered as a true GM flute.

## Accepted R24 media anchors

```text
Candidate manifest:
669d85db980f5c7922c5198dcc1b597b1d85664e543423f2c8570eeafa01fca6

Candidate build report:
d63adcd5e69cf4d96b6daac32c2acb06b6ce0d51ff3514d8802b96d9b6f21741

Resident image:
e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e

Runtime:
ef8f0634ea018a247aac47b17a30fc043403849f0ea235e957db2708f7ebaed3

Proof header:
80d9600baac43c0e19bb02c0de5010b904e2af27636eedff31bec124a7d9e918

Proof source:
fda9c0e3993fd1e10ad6780b679a8c8d519b682d3bb07171c75ca19bf0709851

Deploy BIN:
8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25

Deploy CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

Whole-card guard used for deployment:

```text
593a53aba849ae0fc7e980dccb2299793b29e39dfffd8c6ea4b1772b25952a15
```

Deployment passed the exact pre-write whole-card comparison and the post-write audit with only the fresh R24 directory, BIN and CUE added.

## Immutability

R24 is now an immutable physical baseline.

Do not overwrite or redeploy `SRK-Diagnostics-R24`. All subsequent fidelity work must use a fresh revision and fresh SAROO destination.

## R25 direction

R25 moves from "real song plays correctly through the transport" toward "the song is audibly and observably faithful".

The next tranche must add:

- a visible `elapsed / total` playback timeline and percentage/progress indicator;
- deterministic note-span auditing against the source MIDI;
- explicit early/late Note Off diagnostics rather than relying only on final counts;
- a documented SCSP envelope model using AR/D1R/D2R/RR/DL/KRS fields;
- release-tail lifecycle distinct from logical MIDI key ownership;
- no immediate mixer-zero hard mute on normal Note Off;
- enough physical slots to accommodate active notes plus bounded release tails without stealing;
- final proof that the song still consumes exactly 310 records and terminates with no stuck voices.

General MIDI instrument/tone-bank synthesis remains a later capability after envelope/timing fidelity is physically accepted.
