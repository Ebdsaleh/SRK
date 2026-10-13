# R25 RR16 Calibration Whole-Card Guard PREPARE

Status: **read-only preparation gate**

This gate is the next boundary after the accepted R25 RR16 pre-media result. It
does **not** deploy the candidate and contains no apply path.

## Accepted input

The command re-runs the independent R25 RR16 pre-media gate and therefore
requires the exact Eridu-accepted candidate:

- candidate manifest: `5a282c2ea1077b95ca34bc1fd11593f34cef015baa6da1eb5c5cfe69f830cba9`
- build report: `bcd65a3252e5b7980b2263b4134b8145405cbe043169bcbaacd196a1e708d991`
- calibration image: `f11dd5559b5b1309922679f80fc8c36ed6cf8dc50a6b4073bdcdbaaeb3efe5e5`
- deployable BIN: `a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71`
- deployable CUE: `5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950`
- MODE1 sectors: `144`
- raw track bytes: `338688`

RR16 remains a physical calibration probe only. Production RR remains unset.

## PREPARE sequence

The implementation performs these operations in order:

1. Rejects a guard manifest or receipt located on the mounted SAROO card.
2. Rejects pre-existing evidence paths so an earlier snapshot cannot be
   silently replaced.
3. Re-runs the independent R25 RR16 pre-media gate and requires the exact
   accepted candidate and fresh destination.
4. Creates a fresh complete card inventory using the existing SAROO card-guard
   implementation. The inventory file is written **off-card**.
5. Re-scans the card and requires an exact inventory match.
6. Re-runs the R25 pre-media gate after the snapshot.
7. Re-scans the card again and requires an exact match.
8. Publishes a second off-card preparation receipt binding:
   - exact candidate hashes;
   - exact card-inventory SHA-256;
   - card summary counts;
   - intended category and destination;
   - RR16 / EG1 / EG2 calibration identity;
   - production-RR-unset policy;
   - explicit `saroo_writes: false` and `prepare_only: true` policy.
9. Re-opens and verifies the preparation receipt hash after publication.

The receipt schema is:

`srk.saturn.midi-68k-r25-rr16-guard-prepare-receipt.v1`

## Card access policy

PREPARE may enumerate and read files on the mounted card. It does not create,
replace, remove, rename, truncate, or otherwise modify any card file or
directory.

The only writes are the two caller-selected **off-card** evidence files:

- whole-card inventory manifest;
- R25 bound preparation receipt.

## Deliberately absent

This tranche contains no:

- `--apply` option;
- confirmation token;
- generic deployment call;
- destination directory creation;
- BIN copy;
- CUE copy;
- rollback code, because no card write exists to roll back.

A later APPLY tranche may be designed only after the real card PREPARE output,
guard-manifest SHA-256 and receipt SHA-256 have been reviewed.

## Expected terminal boundary

Successful PREPARE ends with:

```text
Exact final guard          : MATCH
Candidate/card binding     : PASS
Destination freshness      : PASS
SAROO writes               : NONE
Apply path in this command : NONE

Result                     : R25 RR16 PREPARE PASS
Both guard files were created off-card. No SD-card file was modified.
Do not deploy yet; the reviewed APPLY gate is a separate future tranche.
```
