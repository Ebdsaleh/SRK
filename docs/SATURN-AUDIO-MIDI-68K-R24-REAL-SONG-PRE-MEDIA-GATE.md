# R24 real-song independent pre-media gate

R24's physical candidate is not deployable merely because its standalone build
succeeds.  Before any SAROO card write, SRK performs a second, read-only review
of the finished project and mounted-card destination.

## Accepted off-card candidate build

The accepted Eridu build established:

- 310 SRKM records,
- ten queue batches (`32` x 9 + `22`),
- duration `108151354 us`,
- 140 Note On and 140 Note Off records,
- expected peak polyphony 2,
- expected busy allocation count 0,
- expected final active voices 0,
- full final MIDI-state comparison of 256 summary + 1024 controller + 128
  active-note words,
- SH-2 FRT `/128` physical timebase,
- runtime VDP2 PAL/NTSC plus 320/352 clock-group selection,
- original FRT TCR restoration on terminal paths,
- no resident execution, player execution, FRT execution, SCSP MMIO or SAROO
  writes during the build.

Accepted external anchors from that build:

```text
inert manifest
1bd630a124b9fc692ac9d5be30c5b267e419e63899c07a5d8923e1608921302b

inert report
1a8ad5ac0dc18997852af90a6ee746462d2ee15154cad9d2b2df2c2fd3271243

inert BIN
abb9f1c861380cbb80045d6c34aecd92c231db46b7554b0f53905d80ef01aa12

inert CUE
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950

resident image
e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e

candidate main
b4d6f25d3a39150061275a9ab701d3df32063cd0c73015eb9381c4fc7be5b45d

candidate menu
7b36d84223c454999f3d2fecb7af2f17b368843f3dc24931dd1d958b92ad9e8e

candidate runtime
ef8f0634ea018a247aac47b17a30fc043403849f0ea235e957db2708f7ebaed3

proof header
80d9600baac43c0e19bb02c0de5010b904e2af27636eedff31bec124a7d9e918

proof source
fda9c0e3993fd1e10ad6780b679a8c8d519b682d3bb07171c75ca19bf0709851

candidate deploy BIN
8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25

candidate deploy CUE
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The candidate image is 128 MODE1/2352 sectors / 301056 raw bytes.

## What the pre-media gate independently re-proves

The gate:

1. re-parses the exact CC0 `Melody Town Theme.mid` input and validates the fixed
   R24 song profile;
2. reconstructs the full 1408-word expected final MIDI state;
3. re-renders the R24 resident, player, FRT, stream and physical-proof sources;
4. checks each re-rendered hash against external accepted evidence and the files
   stored in the completed candidate;
5. verifies the candidate main/menu/runtime/proof hashes against the external
   Eridu build output, not merely against self-described manifest values;
6. verifies the inert manifest/report/BIN/CUE provenance chain carried into the
   physical candidate;
7. verifies the successful standalone build report still pairs with the current
   candidate manifest and exact deployable BIN/CUE;
8. asks the existing SAROO deployment planner to freshly verify MODE1 geometry
   and require a non-existing destination;
9. returns only a plan.  It has no card-write operation.

The stream producer hashes are also independently pinned to the long-accepted
R22A/R23 representation:

```text
stream source
ce7e48b49381836828f1f40f9205c530a7aa368c407463049416030d8b5d974d

stream header
59c12246a82d0b6341746092cc8facfb374fd8da39db003919ca6c976cdb5e61
```

## Safety boundary

A pre-media PASS is still **not** permission to copy files manually or deploy
from this command.

After a PASS, SRK must take a new whole-card PREPARE guard and compare the exact
mounted-card inventory before an explicit guarded APPLY can be authorized.
The destination is intended to be the fresh path:

```text
D:\saroo\ISO\TEST\SRK-Diagnostics-R24
```

R23 and all earlier physical baselines remain immutable.
