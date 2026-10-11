# Saturn R23 — first MIDI-driven SCSP physical candidate

R23 is the first SRK Saturn milestone allowed to make sound because of a MIDI
record processed by the resident MC68EC000 service.

R22A remains immutable.  Its real-hardware result already proves the corrected
32+8 queue/refill/timestamp service and complete persistent MIDI state.  The R23
candidate is freshly derived from the successful R23 inert full integration,
which itself is cryptographically derived from R22A.

## Scope

The candidate owns only SCSP slot 0 and remains deliberately monophonic.  It
does not steal voices and it does not yet claim sustain-held voice lifetime,
controller-driven mix policy, polyphony, General MIDI instrument selection or a
final hardware-derived scheduler clock.

The R23 resident image is the production-compiler-accepted image:

```text
SHA-256 cb172de4e984dd50fcec195c310cb2945abb10bdaa561d31d52062b7e79038a1
6278 words
12556 bytes
0x00004000-0x0000710C
```

## Physical proof program

The proof is intentionally larger than a two-event beep.  The audio-capable
service must first reproduce the accepted scheduler behavior before it can touch
the first audible MIDI note.

```text
batch 1 / sequence 1
  32 CONTROL_CHANGE records
  channel 3 / CC74
  1000..32000 us

batch 2 / sequence 2
  33000 us   NOTE_ON  channel 3 note 60 velocity 100
  1033000 us NOTE_OFF channel 3 note 60 velocity 64
```

The first batch leaves CC74=31 as a state-persistence witness.

## Required runtime phases

The SH-2 proof must observe, in order:

1. Resident service booted and waiting for a batch.
2. Clock 0: batch 1 accepted but zero records executed.
3. Clock 15000: exactly 15 records executed and no ACK.
4. Clock 32000: sequence 1 ACK, 32 records processed.
5. Publish batch 2 while the clock remains 32000: zero batch-2 records execute.
6. Clock 33000: NOTE_ON executes.
7. MC68EC000 voice-state block matches the expected 15-word key-on state.
8. SH-2 reads the real SCSP slot-0 registers and verifies KYONB, pitch and mixer.
9. The producer clock remains at 33000 while the UI polls for 60 display polls,
   creating an audible observation window without allowing NOTE_OFF to execute.
10. Clock 1033000: NOTE_OFF becomes due and sequence 2 ACKs at read index 2.
11. MC68EC000 voice state matches the expected key-off state.
12. SH-2 verifies SCSP slot-0 KYONB is clear and the mixer is zero.
13. The complete MIDI state is compared: 256 summary words, 1024 controller
    words and 128 active-note words.
14. Final CC74 is still 31, voice key-on count is 1 and key-off count is 1.

Only then may the software report `ACKNOWLEDGED`.

## Audible acceptance

The software can prove that the resident MC68EC000 mutated its voice state and
that the SH-2-visible SCSP slot registers contain the reviewed key-on/key-off
values.  It cannot sense the user's speakers.

Therefore physical R23 acceptance additionally requires the human observation:

```text
a MIDI-driven tone is actually audible during the hold window
and stops at the scheduled Note Off.
```

An ACK without audible sound is not sufficient for physical acceptance.

## Clock claim

R23 keeps the R22A producer-published microsecond clock contract.  The 60-poll
hold is an observation window only.  R23 does **not** claim that the final
hardware-derived time source has been selected or calibrated.

## SCSP access

The resident MC68EC000 uses its SCSP register window at `0x00100000`.  The SH-2
physical verifier inspects the corresponding cache-through main-CPU window at
`0x25B00000` using word reads.  Slot 0 control, pitch and mixer are inspected.

## Safety boundary before deployment

Candidate preparation and full build are off-card only:

```text
SAROO writes                 : NONE
build-time sound CPU start   : NO
build-time Sound-RAM writes  : NO
build-time SCSP MMIO         : NO
```

The runtime behavior becomes active only after a future independent pre-media
gate, guarded deployment to a fresh `SRK-Diagnostics-R23` destination, launch on
real Saturn, entry into `MIDI 68K Audio Proof`, and explicit A press.

Do not manually copy the candidate BIN/CUE to the SD card.
