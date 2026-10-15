# Saturn MIDI / 68K R27 — Physical Acceptance

## Result

R27 Fidelity Pass 1 completed the full Space Spectre stream on real Sega Saturn
hardware without regressing the R26 FIX1 transport baseline.

Final captured diagnostic state:

```text
Space Spectre R27 F1 - 9154 / 16v
Phase 5
Events 9154
Batch 287
Read sequence 287
Read index 2
Last error 0
On 4381
Off 4381
Busy 0
Held 0
Releasing 0
Owned 0
Peak held 10
Peak owned 16
State 1
Space Spectre PASS - 0 dropped notes
```

## Audible qualification

The user reported a clear fidelity improvement over R26 FIX1, so R27's melodic
family mapping and controller-aware mixer changes are accepted as useful.

R27 is **not** accepted as complete percussion fidelity. In the physical Saturn
recording, recognisable percussion is absent compared with the supplied proper
MIDI playback reference. The continuous fan noise in the reference recording is
environmental microphone noise and is excluded from the musical comparison.

R27 therefore becomes the accepted melodic/mixer baseline for R28, while the
R26 FIX1 scheduler/transport remains immutable.

## Next boundary

R28 may change channel-10 percussion source/pitch/loop semantics only. It must
not alter:

- the 9,154-record / 287-batch source stream;
- FIX1 D4 scheduler preservation;
- 16-slot allocator;
- R27 melodic GM-family mapping;
- R27 channel volume/expression/pan behavior;
- final drain/state verification;
- zero-BUSY transport contract.
