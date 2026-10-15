# Saturn MIDI / 68K R28 — Percussion Fidelity Pass 1

## Purpose

R27 physically completed the entire 9,154-event Space Spectre stream and was
audibly better than R26 FIX1, but comparison against the supplied proper MIDI
playback showed no recognisable percussion on the Saturn recording.

The fan noise in the reference recording is treated as environmental microphone
noise and is not a musical reference component.

R28 is deliberately percussion-first. It does not alter the physically accepted
scheduler, batching, D4 FIX1 repair, 16-slot allocator, R27 melodic family
mapping, channel volume/expression handling or pan policy.

## R27 percussion fault model

R27 correctly used GM channel 10 note numbers to choose kick/snare/hi-hat/cymbal
sources, but then also fed those same note numbers through the melodic MIDI pitch
table. A GM percussion note is an instrument selector, not the desired pitch of
the sample.

R27 also used the same continuously looping 100-sample oscillator semantics for
drums as for melodic timbres. This suppresses the sharp transient identity heard
in the proper playback.

## R28 change

For channel 10 only:

- note 35 selects kick and uses fixed calibrated pitch-table index 45;
- note 40 selects snare and uses index 57;
- note 42 selects hi-hat and uses index 69;
- note 51 selects cymbal and uses index 57;
- the four waveforms are deterministic decaying transients;
- samples 96..100 are exactly zero;
- LSA=96 and LEA=100 for percussion;
- the already-proven `NORMAL_LOOP` mode is retained, so after the first transient
  the slot loops a zero-valued tail until ordinary Note Off/release retirement;
- melodic voices explicitly restore LSA=0 / LEA=100 when a percussion slot is
  later reused;
- unused voice-ledger words 24 and 25 count percussion key-ons and retain the
  last drum note for later diagnostic exposure.

No unproven SCSP no-loop mode is introduced.

## Memory layout

R27 data remains unchanged through `0x3EFF`.

R28 adds:

```text
0x3F00..0x3FFF  128-word percussion fixed-pitch table
0x4000..        unchanged resident MC68EC000 program
```

The new table ends exactly at the program boundary and does not overlap it.

## Physical acceptance target

The next Saturn image must retain:

```text
Phase 5
Events 9154
Batch 287
On 4381
Off 4381
Busy 0
Held/Releasing/Owned 0/0/0
Space Spectre PASS - 0 dropped notes
```

Subjectively, the reference drum train should become clearly audible, especially
kick/snare/hat/cymbal attacks that were absent in R27.

Active-voice pitch bend remains deferred.
RR16 remains provisional; production RR remains unset.
