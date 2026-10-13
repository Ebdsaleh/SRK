# Saturn MIDI/68K R25 RR16 Calibration — Guarded APPLY Gate

## Accepted PREPARE evidence

This tranche is bound to the physical Eridu PREPARE result returned on 2026-10-13:

- guard manifest SHA-256: `5c17df50023c47955b4814eea648a506b3c30dafaa50ebfa157de65cffb9eac6`
- preparation receipt SHA-256: `c78b7702f0ed27af0a0f0d42baa4d5754b102adfd1bb148055fb7be960980f6f`
- card files: `1616`
- card directories: `149`
- total file bytes: `60693834694`
- files SHA-256ed: `192`
- intended destination: `D:\saroo\ISO\TEST\SRK-Diagnostics-R25-RR16-CAL`

RR16 remains a calibration probe only. Production RR remains **UNSET**.

## Write boundary

The APPLY command refuses to write unless all reviewed evidence still matches:

1. confirmation token is exactly `DEPLOY-R25-RR16-CALIBRATION`;
2. guard and receipt remain off-card and their canonical digests match the accepted PREPARE values;
3. receipt still binds the exact R25 project, R24 baseline, mounted card, guard path, RR16 policy, category, destination name and fresh destination;
4. the independent R25 pre-media gate passes again;
5. the mounted card matches the whole-card PREPARE inventory immediately before deployment;
6. the destination remains fresh.

Only then is the existing guarded standalone-image deployment primitive called.

## Post-write proof

After deployment SRK requires the exact accepted hashes:

- BIN: `a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71`
- CUE: `5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950`

The post-write whole-card verifier permits only three new paths: the R25 destination directory, its BIN and its CUE. Any unrelated addition, removal, size change or recorded content-hash change fails.

Rollback is deliberately narrow: the new directory is removed automatically only when it still contains exactly the two accepted files with their accepted hashes. Unexpected contents prevent automatic deletion and force manual review.

## Explicit APPLY command

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r25_rr_calibration_guarded_apply ^
  --project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R25-MIDI-RR16-CALIBRATION-FULL-GATE1" ^
  --card-root D:\ ^
  --guard-manifest "C:\Users\Developer.ERIDU\SRK-Workspace\guards\R25-RR16-GATE1-card-inventory.json" ^
  --receipt "C:\Users\Developer.ERIDU\SRK-Workspace\guards\R25-RR16-GATE1-prepare-receipt.json" ^
  --category TEST ^
  --name "SRK-Diagnostics-R25-RR16-CAL" ^
  --confirm DEPLOY-R25-RR16-CALIBRATION
```

Do not recreate, edit or rename either PREPARE JSON before APPLY.

## Required successful terminal boundary

```text
Pre-write whole-card       : MATCH
...
Post-write whole-card      : PASS (only authorised R25 additions differ)

RR / EG1 / EG2             : 16 / 0x001F / 0x3C10
Measurement mode           : OPERATOR-OBSERVED AUDIO
SCSP envelope readback     : NO
Production RR selected     : NO

Result                     : R25 RR16 DEPLOYMENT VERIFIED
Existing SAROO content was not overwritten or removed.
```

Only after this output is reviewed should the card be safely ejected and moved to the Saturn for the RR16 physical listening probe.
