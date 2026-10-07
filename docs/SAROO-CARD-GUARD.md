# SAROO SD-Card Safety Guard

SRK's first real Saturn-firmware write is intentionally gated by an off-card
inventory of the existing SAROO SD card.

The purpose of this guard is to protect unrelated data on a working card — in
particular large game libraries — while avoiding the cost of hashing tens of
gigabytes on every check.

## What the guard records

For every reachable entry on the mounted card, SRK records:

- relative path;
- entry type (`file` or `directory`);
- file size for every file;
- SHA-256 for ordinary files up to 1 MiB;
- SHA-256 for known SAROO control files (`SAROO/ssfirm.bin`, `mcuapp.bin`, and
  `saroocfg.txt`) regardless of size.

The manifest also records file/directory counts, total file bytes, the hash
threshold, and its own SHA-256 integrity value.

This means large game images are checked by path and size instead of being
re-read end-to-end. Small/control files receive content hashing as an additional
integrity check.

## What it does not do

Creating or verifying an inventory does **not**:

- modify the SD card;
- reformat the card;
- create files on the card;
- remove or rename games;
- replace `ssfirm.bin`;
- touch MCU/FPGA firmware;
- hash all game data by default.

The manifest itself must be stored outside the mounted card.

## Baseline snapshot

During development, invoke the module directly so console-entry-point metadata
does not need to be reinstalled after every pull:

```bat
python -m rikai_kotoba.tools.saroo_card_guard snapshot ^
  D:\ ^
  "C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\card_before_srk.json"
```

SRK walks the complete card tree, writes the manifest off-card, and reports the
number of files/directories and total bytes represented.

The command ends with:

```text
The SAROO SD card was not modified.
```

## Exact pre-write verification

Before a later apply operation, the baseline can be rechecked exactly:

```bat
python -m rikai_kotoba.tools.saroo_card_guard verify ^
  D:\ ^
  "C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\card_before_srk.json"
```

Any added, missing, resized, type-changed, or recorded-hash-changed path causes a
non-zero result.

## Post-write verification

After a controlled firmware apply, one reviewed path is expected to differ:

```text
SAROO/ssfirm.bin
```

The same baseline can therefore be verified while allowing only that path:

```bat
python -m rikai_kotoba.tools.saroo_card_guard verify ^
  D:\ ^
  "C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\card_before_srk.json" ^
  --allow-changed-path SAROO/ssfirm.bin
```

All other recorded paths remain protected by the baseline comparison.

## Why SRK does not hash the whole game library

A full content hash of a ~60 GB card would require reading essentially the entire
card before and after a firmware replacement. That is slow, adds unnecessary SD
read traffic, and does not materially improve the safety of an operation whose
authorised write target is one small firmware file.

The guard therefore combines:

- complete path coverage;
- complete file-size coverage;
- selective SHA-256 coverage for small/control files;
- a verified off-card backup of the original `ssfirm.bin`;
- an explicit one-file write target.

This is intended as a practical fail-closed safety layer, not a substitute for a
separate archival backup of irreplaceable user data.
