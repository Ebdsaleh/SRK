# Saturn MIDI / MC68EC000 R20 resident-decoder guarded deployment

This gate is the two-phase media-write boundary for the accepted R20 seven-record resident-decoder candidate.

It reuses the independently accepted R20 pre-media gate and the existing whole-card SAROO inventory/deployment primitives. It does not replace the R17/R18/R19 recovery and physical-acceptance anchors.

## Candidate contract

The candidate remains silent and requires:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     7
LAST_ERROR     0

RD telemetry:
magic          0x5244
version        1
processed      7
current        7
final time     7000 us
ready          1
```

The seven-record proof contains every SRKM v1 opcode exactly once and uses the reviewed release-A / fresh-A trigger interlock.

No MIDI-driven SCSP note is enabled.

## PREPARE

PREPARE is read-only with respect to the mounted SAROO card.

It:

1. reruns the complete R20 pre-media gate;
2. requires the accepted decoder/compiler/BIN/CUE provenance;
3. requires `SRK-Diagnostics-R20` to remain a fresh destination;
4. creates a complete whole-card inventory JSON **off card**;
5. immediately verifies the mounted card against that inventory;
6. performs no card writes.

The resulting inventory SHA-256 is not known in advance and must be reviewed from the real mounted-card PREPARE output.

## APPLY

APPLY is not authorised until PREPARE has passed and its exact manifest SHA-256 has been reviewed.

The R20-specific confirmation token is:

```text
DEPLOY-R20-RESIDENT-DECODER-PROOF
```

APPLY requires both that token and the exact PREPARE manifest SHA-256.

Before writing, APPLY reruns the complete R20 pre-media gate and then requires the whole card to match the PREPARE inventory exactly.

Only these three paths may be introduced:

```text
SAROO/ISO/TEST/SRK-Diagnostics-R20
SAROO/ISO/TEST/SRK-Diagnostics-R20/SRK-Diagnostics.bin
SAROO/ISO/TEST/SRK-Diagnostics-R20/SRK-Diagnostics.cue
```

The deployed BIN and CUE must still match the externally accepted R20 hashes.

After writing, the whole-card inventory verifier permits only those three additions. Any unrelated difference fails the deployment boundary.

## Conservative rollback

Automatic rollback after a post-write failure is permitted only when the newly-created R20 directory still contains exactly the expected BIN and CUE as regular files and both hashes still match the accepted deployment result.

If an unexpected entry, changed hash, symlink, directory or other unknown state is present, automatic deletion is refused.

After an eligible rollback the original PREPARE inventory must verify exactly again.

## Windows path aliases

Allowed-path comparison is based on the stable `SAROO/ISO/...` suffix, so Windows long-profile paths and equivalent 8.3 aliases do not create false unauthorised-difference failures.

## Safety boundary

PREPARE may create only the off-card inventory manifest.

APPLY is the only path in this module allowed to call the existing standalone deployment primitive, and only after:

```text
R20 confirmation token
+ exact reviewed PREPARE manifest SHA
+ complete pre-media PASS
+ exact whole-card pre-write MATCH
```

R17, R18 and R19 remain untouched.
