# Saturn MIDI 68K — R26 FIX1 Physical Acceptance

R26 FIX1 is the accepted real-hardware transport/scheduler baseline for the
Double Impact `Space Spectre` MIDI test.

Physical Sega Saturn terminal evidence reached:

- phase `5` (PASS)
- events `9154`
- batches `287`
- read sequence `287`
- read index `2`
- last error `0`
- Note On `4381`
- Note Off `4381`
- Busy / dropped Note Ons `0`
- final Held / Releasing / Owned `0 / 0 / 0`
- peak Held `10`
- peak Owned `16`
- final state verification `1`
- terminal text `Space Spectre PASS - 0 dropped notes`

The earlier R26 candidate failed after 17 processed records with stream error 7.
FIX1 preserves D4/current MIDI channel across the R25-derived wait/retirement
loop and completed the full 9,154-record stream on hardware.

`Cut:1249` is the resident release-cancel counter, not a dropped-note count. It
includes same-key retriggers that reuse a still-releasing voice as well as true
release-tail capacity steals. The host profile's `release_tail_steals == 12`
counts only the latter capacity-pressure case. `Busy:0` is the physical evidence
that no Note On was rejected.

Musical fidelity is not accepted by this milestone. The R26 bank is explicitly a
synthetic bring-up bank. R27 starts fidelity work without changing the accepted
FIX1 transport path.
