# Saturn Audio/MIDI — R24 Real-SMF Whole-Card Guarded Deployment

## Status

The R24 real-song physical candidate has passed its fresh full build and an
independent read-only pre-media gate on Eridu. This tranche defines the only
permitted route from that accepted off-card evidence to the mounted SAROO card.

It is deliberately two-phase:

1. **PREPARE** — read card + create an off-card whole-card manifest; no card
   writes.
2. **APPLY** — only after the PREPARE manifest SHA-256 has been reviewed; write
   one fresh R24 directory and then prove that no other card path changed.

Never manually copy the R24 BIN/CUE.

## Accepted candidate anchors

The guarded layer binds the independent pre-media result, not merely the build
manifest carried inside the project.

```text
candidate manifest
669d85db980f5c7922c5198dcc1b597b1d85664e543423f2c8570eeafa01fca6

candidate build report
d63adcd5e69cf4d96b6daac32c2acb06b6ce0d51ff3514d8802b96d9b6f21741

candidate main
b4d6f25d3a39150061275a9ab701d3df32063cd0c73015eb9381c4fc7be5b45d

candidate menu
7b36d84223c454999f3d2fecb7af2f17b368843f3dc24931dd1d958b92ad9e8e

runtime after
ef8f0634ea018a247aac47b17a30fc043403849f0ea235e957db2708f7ebaed3

proof header
80d9600baac43c0e19bb02c0de5010b904e2af27636eedff31bec124a7d9e918

proof source
fda9c0e3993fd1e10ad6780b679a8c8d519b682d3bb07171c75ca19bf0709851

deploy BIN
8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25

deploy CUE
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The same guarded command also re-runs the complete independent R24 pre-media
inspection: exact CC0 MIDI, 310 records, ten batches, 140 Note On, 140 Note Off,
peak polyphony two, 1408-word final MIDI state, generated resident/player/FRT/
stream/proof representations and fresh MODE1 verification.

## PREPARE

PREPARE must use a guard manifest stored **outside** the mounted card. The R24
review path is:

```text
C:\Users\Developer.ERIDU\SRK-Workspace\R24-MIDI-REAL-SMF-CARD-BEFORE.json
```

The guard inventory records every directory and file size on the card. Small
files (up to 1 MiB) plus the SAROO control files are SHA-256ed. This proves that
an APPLY did not add/remove/truncate unrelated large game files while still
providing content hashes for the card's small/control surface.

PREPARE order:

```text
re-run independent R24 pre-media
require exact external candidate manifest/report
require R24 destination still fresh
create whole-card manifest off-card
immediately verify card == manifest
report guard manifest SHA-256
SAROO writes = NONE
```

If the guard path already exists, PREPARE refuses to overwrite it.

## APPLY

APPLY is unavailable without all of:

```text
--apply
--expected-guard-manifest-sha256 <reviewed PREPARE digest>
--confirm DEPLOY-R24-REAL-SMF-SONG-PROOF
```

The R24-specific confirmation is checked before media access.

APPLY order:

```text
verify guard document + reviewed SHA
re-run independent R24 pre-media
require external candidate manifest/report again
verify whole card == PREPARE baseline
invoke accepted fresh-directory standalone deployment
verify deployed BIN/CUE hashes
verify whole card allowing exactly three new paths
```

The only authorized path differences are:

```text
SAROO/ISO/TEST/SRK-Diagnostics-R24
SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.bin
SAROO/ISO/TEST/SRK-Diagnostics-R24/SRK-Diagnostics.cue
```

No existing path may be overwritten or removed.

## Rollback restraint

If post-write verification fails, SRK may remove the new R24 directory only if
it can independently prove all of the following:

- the destination is still a directory;
- it contains exactly two regular files;
- those files are the expected BIN and CUE;
- their SHA-256 values still equal the just-deployed artifacts.

If an unexpected third file, non-regular entry, or changed hash is present, SRK
**does not delete the directory automatically**. This avoids destroying evidence
or unrelated data while attempting recovery.

After a safe rollback, the original whole-card guard must verify exactly again.

## Physical stop point

A successful PREPARE is not permission to deploy by itself. Its guard SHA and
card counts must first be reviewed.

A successful APPLY means only that media publication was controlled and the
existing SAROO card was preserved. Physical R24 acceptance still requires the
real Saturn run to demonstrate the ~108-second Melody Town Theme and terminal
contract:

```text
310 records
sequence 10 / index 22
140 Note On / 140 Note Off
peak active voices 2
busy 0
final active 0
state verify PASS
player complete 1 / error 0
voice error 0
```

R23 remains immutable throughout.
