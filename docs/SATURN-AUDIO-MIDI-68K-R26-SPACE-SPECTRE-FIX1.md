# Saturn Audio / MIDI 68K R26 — Space Spectre FIX1

R26 reached real Saturn audio playback but failed very early with resident
**stream error 7 / RECORD** after **17 processed events**. The failure is useful:
the first 32-record batch had already passed resident validation, audio had begun,
and the voice telemetry showed no BUSY/drop condition. The fault therefore lay
inside scheduled application of an already-validated record.

## Root cause

The R25-derived timestamp wait hook runs release-tail retirement while the live
record is waiting for its due time. At that point the record layout is:

- D2:D3 — event timestamp;
- D6 — SRKM opcode;
- **D4 — MIDI channel**;
- D5 — data0;
- D7 — data1.

`_emit_retire_expired()` uses D4 as scratch for release-deadline comparisons.
The old wait hook did not preserve D4. Once a waiting record became due,
`_emit_channel_dispatch()` received the scratch deadline word instead of the
validated MIDI channel and branched to `error_record` (stream error 7).

This exactly matches the physical signature: whole-batch validation succeeded,
17 records were consumed, then the current record failed during application
before batch 0 could be acknowledged.

## FIX1

FIX1 is R26-only. It reserves global voice-ledger word 23 (address `0x232E`),
which sits after the existing R25 globals and before the first R26 slot ledger.
The due-time hook now:

1. stores D4/current MIDI channel to `0x232E` before entering the wait loop;
2. performs the unchanged stable FRT clock read and R25 release retirement;
3. repeats until the event timestamp is due;
4. restores D4 from `0x232E` immediately before channel dispatch.

R24 and R25 generators are untouched. Space Spectre, 16-voice allocation,
release-tail stealing, provisional RR16, FRT timing, all 9,154 events and final
state verification remain unchanged.

## Presentation correction

The first R26 diagnostic inherited an unconditional success sentence from the
R24 screen and could therefore display `Space Spectre PASS - 0 dropped notes`
at the bottom while the proof state above was ERROR.

FIX1 renders:

- PASS text only for proof phase 5;
- `Space Spectre ERROR - see telemetry` for phase 6;
- a running message before either terminal state.

## Fresh off-card build

The failed physical R26 directory is evidence and must never be overwritten.
Build FIX1 into a new project directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r26_fix1_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-PHYSICAL-CANDIDATE-GATE1" ^
  --repository-root "C:\Users\Developer.ERIDU\repos\Python\SRK" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R26-DOUBLE-IMPACT-SPACE-SPECTRE-FIX1-GATE1" ^
  --release-rate 16
```

This command is off-card only. Do not deploy until Eridu has accepted the new
resident/source/build hashes and normal regression suite.
