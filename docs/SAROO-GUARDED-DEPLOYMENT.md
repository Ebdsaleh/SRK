# SAROO Whole-Card Guarded Deployment

SRK's user-facing SAROO firmware write path is guarded by the off-card card
inventory created before deployment.  A firmware hash alone is not enough: the
complete reviewed card topology must match before the write, and every unrelated
path must still match afterward.

## Physically validated baseline — 2026-10-07

On ERIDU, the whole-card guard was physically validated against the user's
existing independently prepared SAROO SD card after the complete SRK suite
passed:

```text
226 tests passed
23 subtests passed
```

The real card baseline contained:

```text
Files           : 1555
Directories     : 127
Total file bytes: 60569378580 bytes (56.41 GiB)
Files SHA-256ed : 149
Manifest SHA-256: d9a2f25460622dec04466af349e8bbec12c300bf697ada6f349ccfb25db9f333
```

An immediate verification of the unchanged card returned:

```text
Result          : MATCH
```

Both commands explicitly reported that the SAROO SD card was not modified.

The reviewed manifest is:

```text
C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\card_before_srk.json
```

The existing working Saturn-side firmware baseline remains preserved separately:

```text
C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\ssfirm_d93c2c91e958a3bf.bin
SHA-256: d93c2c91e958a3bfd125fbf02cccea729ddc8c6f1e1bd9bed298389614880ba7
```

The SRK candidate remains:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK\Firm_Saturn\ssfirm.bin
SHA-256: 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686
```

No real firmware apply had been performed at the time this guarded write path
was introduced.

## Apply gate

The apply command now requires both the reviewed manifest path and the exact
manifest SHA-256 printed when the baseline was created.

Before any card write, SRK requires:

1. the guard manifest to be off-card;
2. the manifest's recorded SHA-256 to equal the reviewed value;
3. the manifest's own payload integrity check to pass;
4. the complete mounted card to match the baseline exactly;
5. the existing `SAROO/ssfirm.bin` SHA-256 to match the reviewed baseline;
6. the candidate SHA-256 to match the reviewed candidate;
7. the verified off-card baseline firmware backup to exist or be safely created.

Only then may SRK replace `SAROO/ssfirm.bin`.

After replacement SRK runs the whole-card guard again.  The only path authorised
to differ is:

```text
SAROO/ssfirm.bin
```

Every other directory, file path, file size, and recorded small/control-file hash
must still match the pre-write baseline.

If the post-write whole-card guard fails, SRK attempts to restore the verified
baseline firmware and then requires the exact original card inventory to match
again before describing the rollback as verified.

## Guarded apply command

```bat
python -m rikai_kotoba.tools.saroo_apply ^
  D:\ ^
  "C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK\Firm_Saturn\ssfirm.bin" ^
  --backup-root "C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO" ^
  --guard-manifest "C:\Users\Developer.ERIDU\SRK-Workspace\Backups\SAROO\card_before_srk.json" ^
  --expected-guard-manifest-sha256 d9a2f25460622dec04466af349e8bbec12c300bf697ada6f349ccfb25db9f333 ^
  --expected-existing-sha256 d93c2c91e958a3bfd125fbf02cccea729ddc8c6f1e1bd9bed298389614880ba7 ^
  --expected-candidate-sha256 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686 ^
  --confirm-write APPLY-SSFIRM
```

This is a real write-capable command.  The user should not remove the card,
power down the reader, or allow another program to write to the card while it is
running.

## Restore gate

Restore also requires the same reviewed whole-card manifest and manifest hash.

Before restore, the guard allows exactly one baseline difference:

```text
SAROO/ssfirm.bin
```

This is the expected state when the SRK candidate is installed.  Any unrelated
change blocks restore before the card is written.

After restoring the known-good baseline firmware, SRK requires the entire card
inventory to match the original pre-SRK baseline exactly.

The current candidate firmware is preserved off-card before restore, as already
required by the preserve-first deployment layer.

## Large game-library protection

The guard deliberately does not SHA-256 every byte of the approximately 56 GiB
game library on each verification.  It records every path, entry type, and file
size, while hashing ordinary files up to 1 MiB and always hashing key SAROO
control files.

This provides a practical before/after integrity boundary for a narrowly scoped
firmware-file replacement without forcing repeated full-card reads.

## Mutation boundary

The guarded deployment authorises only:

```text
SAROO/ssfirm.bin
```

It does not authorise changes to:

- `SAROO/ISO` or any game image;
- `mcuapp.bin`;
- FPGA firmware;
- `saroocfg.txt`;
- the update directory;
- any unrelated directory or file on the card.

Any unrelated inventory difference is a hard guard failure.
