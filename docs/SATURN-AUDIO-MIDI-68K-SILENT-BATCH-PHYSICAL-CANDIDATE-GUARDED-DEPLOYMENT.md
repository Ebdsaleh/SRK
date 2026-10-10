# Saturn Audio / MIDI — R19 Silent Batch Physical Candidate Guarded Deployment

This gate protects the first real-Saturn deployment of the silent 27-record
MC68EC000 candidate.

It deliberately reuses the already accepted R18 media-safety architecture:

```text
independent pre-media gate
-> whole-card PREPARE inventory
-> human review of exact manifest SHA-256
-> explicit R19-specific APPLY token
-> exact pre-write whole-card match
-> isolated fresh-directory deployment
-> exact candidate BIN/CUE verification
-> post-write whole-card allow-list verification
-> conservative automatic rollback only when the new directory is still exact
```

## Accepted R19 candidate anchors

MC68EC000 batch image:

```text
d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5
```

Accepted candidate deployable BIN:

```text
225792 bytes
8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34
```

Accepted candidate CUE:

```text
81 bytes
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

Physical success contract after a later deployment:

```text
ACKNOWLEDGED
READ_SEQUENCE = 1
READ_INDEX = 27
LAST_ERROR = 0
```

The candidate remains silent.  No MIDI-driven SCSP note is enabled.

## PREPARE phase

PREPARE is read-only with respect to the mounted SAROO card.

It first re-runs the independent R19 pre-media gate.  Therefore PREPARE cannot
create a card baseline for a candidate whose manifest/report, generated inputs,
batch-image provenance, guarded UI, PASS contract, MODE1 package or externally
accepted BIN/CUE hashes no longer match.

PREPARE then writes one fresh JSON inventory **off-card** and immediately checks
that inventory back against the entire mounted card.

The inventory must never be stored anywhere under the mounted card root.

PREPARE records the complete card topology and file sizes.  As with the accepted
card guard, small files and the important SAROO firmware/configuration files are
SHA-256 anchored.

No SD-card file is created, deleted, overwritten or renamed by PREPARE.

## APPLY phase

APPLY is unavailable without both:

1. the exact guard-manifest SHA-256 printed by PREPARE; and
2. the R19-specific confirmation token:

```text
DEPLOY-R19-SILENT-BATCH-PROOF
```

The confirmation token is checked before the write path is entered.

APPLY then:

```text
re-runs R19 pre-media validation
-> requires exact whole-card PREPARE baseline match
-> invokes the existing verified standalone-image deployment primitive
-> deploys only a fresh SRK-Diagnostics-R19 directory
-> verifies deployed BIN/CUE hashes
-> verifies whole card again with exactly three authorised changed paths
```

The only authorised post-write differences are:

```text
SAROO/ISO/TEST/SRK-Diagnostics-R19
SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.bin
SAROO/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.cue
```

The path comparison uses the stable `SAROO/ISO/...` suffix so the same physical
Windows path cannot fail solely because one API reports a long user-profile
component and another reports its 8.3 alias.

## Conservative rollback

If a post-write guard fails, automatic rollback is intentionally narrow.

SRK may remove the new R19 directory only when:

```text
the directory still exists
it contains exactly two entries
both entries are regular files
those entries are the expected BIN and CUE
both files still have the exact accepted deployment hashes
```

If any extra entry appears, either hash changes, or a file becomes a non-regular
entry, automatic deletion is refused.

After an eligible rollback the original whole-card PREPARE inventory must verify
exactly again before SRK reports a verified rollback.

## Safety boundary

R17 and R18 remain untouched recovery/acceptance baselines.

The guarded deployment does not alter firmware, configuration, existing games
or existing SRK test directories.

The first user checkpoint for this tranche is **PREPARE only**.  APPLY should not
be issued until the user supplies the complete PREPARE output and the exact guard
manifest SHA-256 has been reviewed.

> Safer is secure, secure is faster. <3
