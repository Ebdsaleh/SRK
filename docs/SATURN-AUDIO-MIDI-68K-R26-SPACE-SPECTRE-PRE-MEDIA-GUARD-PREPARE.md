# Saturn Audio / MIDI 68K R26 — Space Spectre pre-media + whole-card PREPARE

R26 has now reached a successful fresh physical-candidate build for the exact
Double Impact track:

```text
midis/E1M2, E4M3 - Matzu - Space Spectre.mid
SHA-256 984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01
```

The accepted Eridu build produced:

- 9,154 SRKM records / 287 queue batches;
- 4,381 Note On / 4,381 Note Off;
- raw peak polyphony 10;
- 12 release-tail steals;
- zero BUSY/dropped Note Ons;
- R26 resident image SHA-256
  `7bcc139b2a689f77f03de79c0efae5e018e3584bfe15826baafa09c7aef32b40`;
- deployable MODE1/2352 BIN SHA-256
  `4e1e45c411c78a1b08460e788ca4667044d2fed8769fc2d182da878e17ad47d7`;
- 208 sectors / 489,216 raw bytes / 425,984 user bytes.

RR16 remains a provisional bring-up value. Production RR is still **UNSET**.

## Independent pre-media gate

`midi_68k_r26_pre_media_gate.py` does not trust only the successful build
result. It independently:

1. verifies the candidate manifest/generated-file inventory;
2. verifies the exact physically accepted R24 baseline;
3. re-profiles the locked Space Spectre source;
4. re-generates the complete R26 resident/player/proof representation;
5. re-derives main/menu from the accepted R24 baseline;
6. reconstructs the generated runtime byte-for-byte;
7. verifies the successful standalone build/report pairing;
8. pins the Eridu-accepted build BIN/ISO/MAP, packaged PCM and deployable
   BIN/CUE;
9. verifies MODE1 geometry;
10. invokes only the existing read-only SAROO fresh-destination planner.

The first independent review reports the candidate manifest and build-report
SHA-256 values. They are then bound into the PREPARE receipt and may be pinned by
the separate guarded APPLY tranche.

There is no deployment operation in the pre-media module.

## Whole-card PREPARE

`midi_68k_r26_guard_prepare.py` performs:

1. independent R26 pre-media review;
2. fresh whole-card inventory written off-card;
3. exact inventory verification;
4. second independent pre-media review;
5. second exact whole-card verification;
6. canonical off-card receipt binding candidate + card + destination.

The receipt explicitly records:

- exact manifest/report hashes;
- exact R26 generated/build/deployable hashes;
- the full whole-card guard hash and counts;
- future fresh destination;
- `prepare_only = true`;
- `saroo_writes = false`;
- `apply_available_in_this_module = false`.

No file on the mounted SAROO card is created, replaced or removed by PREPARE.

## Intended destination

```text
D:\saroo\ISO\TEST\SRK-Diagnostics-R26-Space-Spectre
```

The planner must report this destination as fresh.

## Safety boundary

This tranche still has **no APPLY path**.

Only after Eridu returns:

- a passing pre-media result;
- exact candidate manifest/report SHA-256;
- exact whole-card guard SHA-256 and counts;
- exact canonical PREPARE receipt SHA-256;

should a separate guarded APPLY tranche be written. That APPLY must permit only
the new destination directory plus its exact BIN/CUE, and must verify the whole
card again after the write.

Safer is secure, secure is faster.
