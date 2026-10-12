# Saturn Audio/MIDI — R25 Playback Fidelity Source Gate

R24 physically proved that a complete real Standard MIDI File can be scheduled,
streamed, played and terminated correctly on a Sega Saturn. R25 now targets the
human-facing and synthesis-quality gaps exposed by that first real-song run.

## Why R25 exists

The R24 physical result reached:

```text
310 records
10 batches
140 Note On
140 Note Off
peak voices 2
busy 0
active 0
state verify PASS
voice error 0
Song PASS
```

The song stopped normally at the PASS screen, so the stream was not looping.
However, the physical observer had no elapsed/total timeline and some note endings
sounded unusually abrupt.

The abruptness is not evidence that the R24 scheduler dropped Note Off events. R24
counted all 140 Note On and 140 Note Off events and finished with zero active voices.
The source MIDI also genuinely contains many short notes: the reference sequence has
22 note spans around 211 ms and 50 around 423 ms.

There is nevertheless a deliberate R24 synthesis limitation that makes those short
notes harsher than a musical instrument: normal R24 Note Off performs SCSP KEY_OFF
and then immediately sets the slot mixer to zero. That is a hard mute.

The official SCSP envelope generator provides Attack, Decay-1, Decay-2 and Release
states. KEY_OFF transitions to the release segment and RR controls attenuation. R25
therefore separates logical MIDI key ownership from audible release-tail ownership.

## Source/model additions

### Exact note-span audit

`midi_68k_r25_note_audit.py` pairs normalized SRKM Note On/Off records without
changing timestamps.

It reports:

- minimum / median / maximum source note duration;
- number of sub-250-ms notes;
- active+release slot pressure for a target release window;
- a conservative 500-ms release-tail capacity audit.

R25 owns four SCSP slots in the planned fidelity engine. The reference song must fit
within that no-steal pool even after bounded release tails are included.

Initial human target:

```text
release-tail target : 120000 us
owned slots         : 4
stealing            : disabled
```

The target is a musical-policy goal, not yet a claimed hardware RR calibration.

### Playback timeline

`midi_68k_r25_progress.py` adds a deterministic screen model such as:

```text
00:54.075/01:48.151  50%
Events 155/310
Batch 05/10
[##########----------]
```

The elapsed value clamps at total duration after the final event so terminal polling
latency cannot make the UI appear to overrun the song.

A future R25 physical proof must display progress continuously while playback is
running so a human can immediately distinguish a one-shot song from a loop.

### SCSP envelope register model

`midi_68k_r25_envelope.py` models the documented slot EG registers:

```text
+08h : D2R[4:0] D1R[4:0] EGHOLD AR[4:0]
+0Ah : LPSLNK KRS[3:0] DL[4:0] RR[4:0]
```

The initial sustain/release shape is structurally:

```text
AR   = 0x1F  fast attack
D1R  = 0     no decay-1 attenuation
D2R  = 0     sustain instead of continuing decay
KRS  = 0xF   key-rate scaling off
DL   = 0
RR   = explicit calibration input
```

R25 intentionally does **not** guess which RR value equals 120 ms on physical
hardware. The next compiler/physical calibration tranche must select and measure RR
before a value becomes accepted policy.

Normal R25 Note Off policy must not immediately zero the mixer. It must issue KEY_OFF
and allow the envelope release segment to become audible, then recycle the slot only
when the bounded release lifecycle says it is safe.

### Held/releasing lifecycle

`midi_68k_r25_release_lifecycle.py` now models the complete four-slot ownership
contract before it is rendered into MC68EC000 code:

```text
FREE -> HELD -> RELEASING -> FREE
```

At every event timestamp, expired release tails are retired before new allocation.
A matching-key retrigger reclaims that key's existing held or releasing slot. A new
key uses the lowest free slot. If all four slots remain owned, the event reports
BUSY and never steals another key.

For the exact reference song with the 120-ms target lifecycle, the model records:

```text
Note On                 140
Note Off                140
release tails started   140
release tails completed 138
release tails cancelled 2 (same-key retrigger)
busy                    0
peak held               2
peak releasing          1
peak total owned        2
final owned             0
```

The cancelled count is intentional and observable: two notes retrigger while their
previous release tail is still owned. The invariant is therefore `completed +
cancelled == started`, rather than incorrectly requiring every tail to decay fully.

### Event-timing telemetry

`midi_68k_r25_timing.py` defines source-vs-observed timing observations with signed
microsecond error. It reports exact, early and late counts, maximum early/late and
absolute error, plus violations against an explicit tolerance. The model does not
choose a physical tolerance; that belongs to the later hardware gate.

### RR calibration matrix

`midi_68k_r25_rr_calibration.py` renders all 32 legal RR values and their exact EG1
and EG2 register words. Selection is fail-closed: no RR can become R25 policy until
the caller supplies positive physical release-duration measurements. The nearest
measured release to the 120-ms target wins, with the lower RR as a deterministic tie
break only when two measured errors are equal.

`midi_68k_r25_fidelity.py` combines note-span auditing, the full release lifecycle,
five deterministic progress checkpoints and the unmeasured RR matrix into one
reference-song acceptance profile.

## R24 remains immutable

The physically accepted R24 destination and media are never modified:

```text
saroo/ISO/TEST/SRK-Diagnostics-R24
BIN 8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25
CUE 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

R25 must derive into fresh source/build/media destinations.

## Next gate after this source/model tranche

Once Eridu validates this expanded source/model gate, proceed as one substantial
hardware-integration tranche:

1. render the four-slot resident MC68EC000 service;
2. expose HELD vs RELEASING ownership and release counters in its voice ledger;
3. compile all 32 inert RR variants without hardware I/O;
4. render the live `elapsed / total` timeline into the Saturn proof screen;
5. add early/late Note Off timing telemetry;
6. run a fresh inert standalone build;
7. then build a fresh physical R25 calibration/song candidate.

Steps 1 through 3 are implemented by the R25 resident-service compiler gate.
They remain pending Eridu's legacy compiler evidence; no RR value is selected
and no physical candidate is produced at this point.

Physical R25 acceptance will require both machine proof and human observation:

```text
full 310-event song still completes
+ timeline visibly advances to 01:48.151 / 100%
+ no dropped Note On/Off
+ release tails do not consume more than owned slots
+ no stuck voice
+ short notes no longer end as hard mixer mutes
+ timing remains source-faithful
```

GM flute/tone-bank synthesis remains separate from this envelope/timing-fidelity
milestone.
