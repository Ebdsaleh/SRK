# SAROO Saturn-Firmware Deployment Safety

SRK treats firmware already present on a user's SAROO SD card as an
**independent baseline**. It does not assume that an existing card was created
from SRK files or from the same upstream SAROO revision used by an SRK research
build.

This distinction matters because a working third-party or previously prepared
card is valuable recovery evidence.

## Deployment stages

SRK separates deployment into four explicit stages:

1. **plan** — read-only comparison of existing card firmware and a candidate;
2. **backup** — create and verify an off-card copy while leaving the card unchanged;
3. **apply** — backup-first, hash-gated replacement of modern `SAROO/ssfirm.bin`;
4. **restore** — verified return to an off-card baseline backup.

Planning never writes. Backup writes only to the off-card preservation directory.
Apply and restore are separate commands and require full SHA-256 values from a
previously reviewed state plus an explicit confirmation token.

SRK does not deploy or modify MCU firmware, FPGA firmware, configuration files,
game images, or the SAROO update directory as part of this workflow.

## Physical planning validation — 2026-10-07

The read-only planner was physically validated on ERIDU against an existing,
independently prepared SAROO SD card after the full SRK suite passed:

```text
205 tests passed
23 subtests passed
```

The mounted card was detected as the unambiguous modern layout. Its existing
working Saturn-side firmware was:

```text
SAROO/ssfirm.bin
size:    447357 bytes
SHA-256: d93c2c91e958a3bfd125fbf02cccea729ddc8c6f1e1bd9bed298389614880ba7
```

The separately built SRK capture candidate was:

```text
size:    484246 bytes
SHA-256: 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686
```

The planner proposed the off-card baseline backup:

```text
SRK-Workspace/Backups/SAROO/ssfirm_d93c2c91e958a3bf.bin
```

and completed with no backup creation and no SD-card modification. This physical
checkpoint is the evidence used to permit development of backup/apply/restore;
it is not itself evidence that write-capable deployment has yet been physically
exercised.

## Modern layout gate

Automatic deployment is currently gated to the unambiguous modern layout:

```text
<SAROO SD root>/
└── SAROO/
    └── ssfirm.bin
```

Legacy root `ramimage.bin`, mixed layouts, and unrecognised layouts are reported
but are not authorised for backup/apply/restore.

This is intentional. SRK must not guess which Saturn-side firmware file a real
cartridge boots.

## Read-only planning

Given:

- a mounted SAROO SD-card root;
- a newly built candidate Saturn-side firmware file;
- an off-card backup directory;

SRK records:

- existing card firmware path, size, and SHA-256;
- candidate path, size, and SHA-256;
- whether replacement is actually needed;
- proposed off-card backup path;
- whether a matching backup already exists;
- whether the evidence is sufficient for an explicit apply.

The planner proposes a deterministic content-addressed backup filename:

```text
SRK-Workspace/Backups/SAROO/ssfirm_<first-16-hash-chars>.bin
```

The full SHA-256 is still checked; the shortened hash is used only in the
filename.

If the proposed backup already exists:

- matching content is recognised as an already-valid backup;
- different content blocks the apply gate;
- SRK never overwrites the conflicting file.

Plan command:

```bat
python -m rikai_kotoba.tools.saroo_deployment ^
  D:\ ^
  "C:\path\to\SAROO-SRK\Firm_Saturn\ssfirm.bin" ^
  --backup-root "C:\path\to\safe\off-card\backups"
```

Planning ends with:

```text
No backup was created. No SD-card file was modified.
```

## Standalone verified backup checkpoint

Before the first physical apply, SRK can create the baseline backup in a separate
checkpoint while leaving the SD card unchanged. This is intentionally available
as a module command even when console-script metadata has not been reinstalled:

```bat
python -m rikai_kotoba.tools.saroo_backup ^
  D:\ ^
  --backup-root "C:\path\to\safe\off-card\backups" ^
  --expected-existing-sha256 <64-character-existing-hash>
```

The command re-inspects the modern card layout, requires the full reviewed
existing-firmware hash, creates or reuses the deterministic content-addressed
backup, verifies the backup SHA-256, then re-hashes the card source again. It
ends by stating that the SAROO SD card was not modified.

This checkpoint is recommended before the first real write to a previously
working independent SAROO card.

## Explicit apply

Apply requires the full existing-card and candidate SHA-256 values from the
reviewed plan. If either file has changed since planning, apply fails before
creating a backup or modifying the card.

Before `SAROO/ssfirm.bin` is replaced, SRK:

1. re-inspects the card and requires exactly one modern firmware file;
2. re-hashes existing card firmware and candidate firmware;
3. creates or re-verifies the off-card backup;
4. re-reads and SHA-256-verifies that backup;
5. stages the candidate beside the destination on the SD card;
6. verifies the staged candidate hash;
7. re-checks the live destination hash immediately before replacement;
8. replaces only `SAROO/ssfirm.bin`;
9. re-reads the installed file and verifies the candidate SHA-256.

If post-write verification fails, SRK attempts to restore the verified baseline
backup immediately and reports whether rollback could be verified.

The write-capable command requires the exact confirmation token
`APPLY-SSFIRM`:

```bat
python -m rikai_kotoba.tools.saroo_apply ^
  D:\ ^
  "C:\path\to\SAROO-SRK\Firm_Saturn\ssfirm.bin" ^
  --backup-root "C:\path\to\safe\off-card\backups" ^
  --expected-existing-sha256 <64-character-existing-hash> ^
  --expected-candidate-sha256 <64-character-candidate-hash> ^
  --confirm-write APPLY-SSFIRM
```

The confirmation token is deliberately separate from the hash gates. A command
copied from an older plan still fails closed if the current bytes no longer
match.

## Explicit restore

Restore uses the verified off-card baseline backup. Before returning that
baseline to the card, SRK preserves the currently installed firmware off-card as
another content-addressed archive:

```text
ssfirm_pre_restore_<first-16-current-hash-chars>.bin
```

Restore then stages and verifies the baseline, replaces only
`SAROO/ssfirm.bin`, and verifies the final card hash.

The restore command requires the exact confirmation token `RESTORE-SSFIRM`:

```bat
python -m rikai_kotoba.tools.saroo_restore ^
  D:\ ^
  "C:\path\to\safe\off-card\backups\ssfirm_<hash-prefix>.bin" ^
  --expected-current-sha256 <64-character-current-hash> ^
  --expected-backup-sha256 <64-character-baseline-hash> ^
  --confirm-restore RESTORE-SSFIRM
```

An optional `--archive-root` can place the pre-restore current-firmware archive
in another off-card directory.

## Off-card preservation policy

Candidate firmware, baseline backups, and pre-restore archives must all live
outside the mounted SAROO SD card. SRK rejects card-resident candidate or backup
locations.

Backup and archive files are never silently overwritten. Existing files are
reused only if their SHA-256 exactly matches the bytes that SRK intends to
preserve.

## Failure model

The workflow is designed to fail closed:

- unexpected layout -> no write;
- stale existing-card hash -> no write;
- stale candidate hash -> no write;
- conflicting backup -> no write;
- stale staging file -> no write;
- backup verification failure -> no card modification;
- destination changes between validation and replacement -> no replacement;
- post-write candidate verification failure -> verified-baseline rollback is
  attempted immediately.

Removing the SD card, losing power, filesystem/media failure, or hardware failure
can never be made completely risk-free by software. The verified off-card backup
exists specifically so the original working bytes remain recoverable even if the
card itself later has to be repaired or recreated.

## Console entry points

Fresh package installation exposes the existing planner/apply/restore scripts:

```text
srk-saroo-deployment
srk-saroo-apply
srk-saroo-restore
```

The standalone baseline backup is currently invoked directly as:

```text
python -m rikai_kotoba.tools.saroo_backup
```

During development, `python -m rikai_kotoba.tools.<module>` is preferred after a
pull because it does not depend on reinstalling console-script metadata.
