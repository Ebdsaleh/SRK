# Saturn Audio / MIDI 68K R26 — Double Impact physical full-build gate

R26 now targets the supplied Double Impact track **Space Spectre** directly on
Saturn rather than another synthetic single-note calibration.

The source-engine evidence accepted on Eridu is pinned exactly:

- source SHA-256 `984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01`;
- 9,154 SRKM records in 287 batches;
- 4,381 Note On and 4,381 Note Off records;
- 148,093,750 us source duration;
- raw peak polyphony 10;
- 16-slot R25-tail peak ownership;
- 12 release-tail steals;
- **0 dropped/busy Note On allocations**;
- R26 resident image SHA-256 `7bcc139b2a689f77f03de79c0efae5e018e3584bfe15826baafa09c7aef32b40`;
- 31,685 resident words / 63,370 bytes.

## Physical behavior

The candidate reuses the accepted R24 SH-2 FRT `/128` runtime clock and mailbox
refill path. The R26 producer publishes all 287 batches from the exact locked
SMF, while the MC68EC000 resident service selects eight synthetic melodic timbre
families plus dedicated channel-10 percussion.

The provisional RR16 value is carried forward only because that exact R26 image
was accepted by the source gate. **Production RR remains UNSET.** Musical
playback, not further single-note RR probing, is the active milestone.

After the final batch is acknowledged the proof enters a DRAINING phase. The
SH-2 continues publishing clock samples until the resident voice ledger reports
held=0, releasing=0 and owned=0. Only then does it verify the complete final
MIDI state and report PASS.

## Fresh off-card build

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r26_physical_candidate_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-PHYSICAL-CANDIDATE-GATE1" ^
  --repository-root "C:\Users\Developer.ERIDU\repos\Python\SRK" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R26-DOUBLE-IMPACT-SPACE-SPECTRE-FULL-GATE1" ^
  --release-rate 16
```

The output directory must not already exist. The command performs no Saturn
hardware I/O and no SAROO write. A successful build is still off-card evidence;
independent pre-media and whole-card guard gates are required before deployment.
