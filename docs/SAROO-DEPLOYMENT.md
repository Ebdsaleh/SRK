# SAROO Saturn-Firmware Deployment Safety

SRK treats firmware already present on a user's SAROO SD card as an
**independent baseline**. It does not assume that an existing card was created
from SRK files or from the same upstream SAROO revision used by an SRK research
build.

This distinction matters because a working third-party or previously prepared
card is valuable recovery evidence.

## Current stage: planning only

The current deployment workflow is deliberately read-only.

Given:

- a mounted SAROO SD-card root;
- a newly built candidate Saturn-side firmware file;
- an off-card backup directory;

SRK can compare the existing card firmware and the candidate, then print the
exact backup/destination plan that a later explicit apply operation would need.

It does **not** currently:

- create the backup directory;
- copy the existing firmware;
- replace `ssfirm.bin`;
- rename card files;
- touch MCU firmware;
- touch FPGA firmware;
- use the SAROO update directory;
- flash cartridge hardware.

## Modern layout gate

Automatic future deployment design is currently gated to the unambiguous modern
layout:

```text
<SAROO SD root>/
└── SAROO/
    └── ssfirm.bin
```

Legacy root `ramimage.bin`, mixed layouts, and unrecognised layouts are reported
but are not authorised for an apply path.

This is intentional. SRK must not guess which Saturn-side firmware file a real
cartridge boots.

## Off-card backup policy

Before a future apply operation can replace `SAROO/ssfirm.bin`, SRK must first
preserve the existing file outside the mounted SD card.

The read-only planner proposes a deterministic content-addressed filename:

```text
SRK-Workspace/Backups/SAROO/ssfirm_<first-16-hash-chars>.bin
```

The full SHA-256 is still recorded and checked; the shortened hash is used only
in the filename.

If the proposed backup already exists:

- matching content is recognised as an already-valid backup;
- different content blocks the future apply gate;
- SRK never overwrites the conflicting file during planning.

## Candidate policy

The candidate firmware must be outside the mounted SAROO SD card. This prevents
the planner from accidentally treating a card-resident file as an independent
build artifact.

The planner records:

- existing card firmware path, size, and SHA-256;
- candidate path, size, and SHA-256;
- whether replacement is actually needed;
- proposed off-card backup path;
- whether a matching backup already exists;
- whether the evidence is sufficient to design a later explicit apply action.

If the candidate is byte-identical to the existing firmware, replacement is
reported as unnecessary.

## Command

After pulling the current source, the module can always be run directly from an
active editable SRK environment:

```bat
python -m rikai_kotoba.tools.saroo_deployment ^
  D:\ ^
  "C:\path\to\SAROO-SRK\Firm_Saturn\ssfirm.bin"
```

Replace `D:` with the mounted SAROO card drive.

A fresh editable install also exposes:

```bat
srk-saroo-deployment D:\ "C:\path\to\ssfirm.bin"
```

Optional backup-root override:

```bat
srk-saroo-deployment D:\ "C:\path\to\ssfirm.bin" ^
  --backup-root "C:\path\to\safe\off-card\backups"
```

The command ends by stating:

```text
No backup was created. No SD-card file was modified.
```

## Future apply requirements

A write-capable deployment command should not be added until the planner has
been physically validated against the user's real card and candidate build.

When implemented, the apply path should require all of the following:

1. unambiguous modern layout;
2. existing firmware hash still matches the plan;
3. candidate hash still matches the plan;
4. backup location is outside the card;
5. existing firmware is copied to backup first;
6. backup size/hash are verified before replacement;
7. replacement is explicit, never implicit;
8. written card firmware is re-read and hash-verified;
9. MCU/FPGA firmware remains untouched;
10. restore remains possible from the verified backup.

Until then, SRK remains at the read-only planning gate.
