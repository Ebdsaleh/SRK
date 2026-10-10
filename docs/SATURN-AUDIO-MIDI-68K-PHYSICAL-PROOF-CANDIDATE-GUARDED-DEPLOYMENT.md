# Saturn Audio — R18 Silent MIDI/MC68EC000 Candidate Guarded Deployment

## Purpose

This is the final media boundary before the first real-Saturn silent
MIDI/MC68EC000 acknowledgement proof.

The workflow is intentionally split into two phases:

```text
PREPARE
  -> re-run independent pre-media proof
  -> create fresh whole-card inventory off the SAROO card
  -> verify that inventory immediately
  -> NO card write

APPLY
  -> require exact reviewed inventory SHA-256
  -> require R18-specific confirmation token
  -> re-run independent pre-media proof again
  -> require card still matches pre-write inventory exactly
  -> deploy one new R18 directory only
  -> verify destination BIN/CUE hashes
  -> verify whole card allowing only exact R18 additions
```

PREPARE is the required next checkpoint. A PREPARE pass does not itself
authorize or perform deployment.

## Accepted R18 candidate

The externally accepted deployable artifacts are:

```text
BIN
188160 bytes
SHA-256 8295455d79b96d7263175bb4e0107ffbe021d8f644fb3bc2df3554d65b60b9df

CUE
81 bytes
SHA-256 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The independent pre-media gate already proved:

```text
candidate provenance      PASS
proof UI/call path        VERIFIED
A-release/fresh-A trigger VERIFIED
MODE1 verification        PASS
external artifact hashes  PASS
SAROO destination         FRESH
SAROO writes              NONE
```

The guarded deployment reruns those checks again in both PREPARE and APPLY.

## Whole-card inventory

The PREPARE phase uses SRK's existing SAROO card inventory guard.

The inventory is always written **off the mounted card** and records:

```text
complete directory/file topology
every file size
SHA-256 for small/control files
always-hashed SAROO firmware/config control files
```

This preserves the established guard policy without reading/hash-processing all
large game images on every verification pass.

The manifest contains its own SHA-256. APPLY requires the user to supply that
exact digest independently.

If any unapproved path, size or recorded hash changes between PREPARE and APPLY,
APPLY refuses to cross the media-write boundary.

## Unique write confirmation

The only accepted high-level confirmation token is:

```text
DEPLOY-R18-SILENT-PROOF
```

The token is checked before any card write.

The generic standalone-image deployment token remains an internal implementation
detail of the already-reviewed new-directory-only copier.

## Destination boundary

The intended destination is:

```text
SAROO/ISO/TEST/SRK-Diagnostics-R18
```

The existing standalone image deployment primitive already requires:

```text
modern SAROO layout
existing TEST category
fresh destination
no stale .srk-pending path
successful standalone build report
verified MODE1/2352 BIN/CUE
single-track CUE contract
fresh BIN/ISO verification
new-directory-only deployment
source/destination SHA-256 equality
```

It does not overwrite or remove existing game directories.

## Post-write whole-card boundary

After a successful copy, the original pre-write inventory is verified again.

Only these three additions are authorised to differ:

```text
SAROO/ISO/TEST/SRK-Diagnostics-R18
SAROO/ISO/TEST/SRK-Diagnostics-R18/SRK-Diagnostics.bin
SAROO/ISO/TEST/SRK-Diagnostics-R18/SRK-Diagnostics.cue
```

Every other path remains subject to the original inventory.

A successful final boundary is:

```text
pre-write whole-card   MATCH
destination BIN hash   exact accepted R18 hash
destination CUE hash   exact accepted R18 hash
post-write whole-card  PASS with only the three authorised additions
```

## Failure and rollback policy

The normal standalone deployment uses a hidden pending directory and removes it
if the copy fails before publication.

If the copy publishes successfully but the final whole-card guard fails, the
R18 wrapper may remove the new destination automatically **only if** all of the
following remain true:

```text
destination is still a directory
it contains exactly two regular files
those files are exactly the expected BIN and CUE
their SHA-256 hashes still equal the deployed accepted artifacts
```

After removal the original whole-card inventory must verify exactly.

If an unexpected file, directory, symlink or changed candidate hash appears
inside the new destination, SRK refuses automatic deletion. This is deliberate:
a rollback must never risk deleting data that is no longer provably SRK's own
isolated deployment.

## PREPARE command

After the source gate is green:

```text
python -m rikai_kotoba.tools.saturn_midi_68k_physical_proof_candidate_guarded_deployment \
  --project <accepted-R18-candidate> \
  --card-root D:\ \
  --guard-manifest <fresh-off-card-manifest.json> \
  --category TEST \
  --name SRK-Diagnostics-R18 \
  --expected-bin-sha256 8295455d79b96d7263175bb4e0107ffbe021d8f644fb3bc2df3554d65b60b9df \
  --expected-cue-sha256 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

No `--apply` is present.

Expected terminal boundary:

```text
Exact pre-write guard   : MATCH
SAROO writes            : NONE
Result                  : READY FOR EXPLICIT R18 APPLY
```

The printed guard-manifest path and SHA-256 must be preserved for review.

## APPLY phase — deliberately separate

APPLY is not the next command in this document's current checkpoint.

After PREPARE output is reviewed, a later command will require:

```text
--apply
--expected-guard-manifest-sha256 <exact PREPARE digest>
--confirm DEPLOY-R18-SILENT-PROOF
```

No hash is guessed or copied from an unreviewed source.

## After verified R18 deployment

Safely eject the SD card before moving it to the Saturn.

The first physical test remains silent:

```text
boot R18
-> enter MIDI 68K Silent Proof
-> release A
-> fresh A press once
```

Physical PASS remains exactly:

```text
ACKNOWLEDGED
READ_SEQUENCE = 1
READ_INDEX    = 1
LAST_ERROR    = 0
```

No MIDI-driven SCSP note is attempted until that round trip is physically
accepted.

R17 remains the accepted known-good physical recovery baseline.

> Safer is secure, secure is faster.
