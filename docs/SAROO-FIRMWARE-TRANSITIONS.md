# Guarded SAROO research-firmware transitions

SRK treats the first successful whole-card-guarded SAROO deployment differently
from later research-firmware revisions.

The original whole-card manifest remains the authority for every unrelated card
path. Later research sessions may legitimately differ at these exact SRK paths:

```text
SAROO/ssfirm.bin
SAROO/SRK_WRAML.BIN
SAROO/SRK_WRAMH.BIN
```

`SAROO/ssfirm.bin` must always match the exact reviewed currently accepted
firmware SHA-256 before a transition. If either Work RAM capture file exists, it
must be an ordinary file of exactly 1 MiB before SRK exempts that path from the
original baseline comparison.

## Physically accepted starting firmware

The first SRK Saturn-side firmware was physically accepted on real hardware on
2026-10-07 after:

- whole-card pre-write guard `MATCH`;
- whole-card post-write guard `MATCH` with only `SAROO/ssfirm.bin` allowed;
- independent installed-firmware hash verification;
- normal SAROO boot on the Sega Saturn;
- existing game-library visibility and successful game operation.

Accepted firmware:

```text
size:    484246 bytes
SHA-256: 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686
```

This accepted build was preserved off-card before the next research transition.

## Controller-capture firmware

The separate generated tree:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-CAPTURE
```

was prepared and built on ERIDU without modifying the accepted `SAROO-SRK`
generated tree.

Build artifact:

```text
ssfirm.bin
  484246 bytes
  SHA-256 28c154b415b570d1d3075fbe5fa5cd1bb51ab5ef511fe9a0318f43c97c783d95
```

The guarded accepted-firmware transition from `7f30e1a5...` to `28c154b4...`
completed with both pre- and post-transition guards matching. The new firmware
then booted on the real Sega Saturn and exposed:

```text
SRK Capture WRAM-L
SRK Capture WRAM-H
```

Both menu actions were physically exercised successfully and produced exact
1 MiB SD-card files. See `SAROO-HARDWARE-CAPTURE.md` for the recorded hashes and
content observations.

## Transition safety contract

`transition_saroo_firmware_guarded()` requires:

1. the original reviewed off-card whole-card guard manifest;
2. the exact reviewed manifest SHA-256;
3. the exact SHA-256 of the currently accepted firmware;
4. the exact SHA-256 of the candidate firmware;
5. a backup root outside the card;
6. every unrelated card path to match the original baseline.

Before and after a transition, SRK may exempt only:

```text
SAROO/ssfirm.bin
SAROO/SRK_WRAML.BIN
SAROO/SRK_WRAMH.BIN
```

The capture-output exemptions are conditional: any present WRAM file must still
be exactly 1 MiB. A missing capture file is acceptable because captures are
session artifacts rather than required firmware components.

The transition then:

1. validates any present SRK Work RAM output files;
2. verifies the card against the original manifest with only the reviewed SRK
   research paths exempted;
3. verifies that the live `ssfirm.bin` hash exactly matches the accepted current
   firmware hash;
4. creates or reuses a content-addressed verified off-card backup of the current
   firmware;
5. stages and verifies the candidate beside the live destination;
6. re-checks the live current firmware immediately before replacement;
7. replaces only `SAROO/ssfirm.bin`;
8. verifies the installed candidate SHA-256;
9. validates the SRK capture outputs again;
10. verifies every unrelated card path against the original baseline again.

If post-transition verification fails, SRK attempts to restore the just-preserved
accepted firmware and verifies both its hash and the guarded card state.

## Explicit command

For an already installed accepted research firmware, use:

```bat
python -m rikai_kotoba.tools.saroo_transition ^
  D:\ ^
  "C:\path\to\new\ssfirm.bin" ^
  --backup-root "C:\path\to\off-card\backups" ^
  --guard-manifest "C:\path\to\card_before_srk.json" ^
  --expected-guard-manifest-sha256 <full-manifest-sha256> ^
  --expected-current-sha256 <full-current-firmware-sha256> ^
  --expected-candidate-sha256 <full-candidate-sha256> ^
  --confirm-transition TRANSITION-SSFIRM
```

Do not use the first-deployment `srk-saroo-apply` command for later accepted
research-firmware revisions. The transition command exists specifically because
the card now contains reviewed research-state differences from the original
baseline.

## Capture files remain separate research evidence

Allowing the two exact Work RAM filenames through a later firmware-transition
guard does not make them firmware. They remain runtime evidence produced by
explicit capture actions.

Host-side ingestion should copy them into SRK's immutable off-card CaptureStore:

```bat
python -m rikai_kotoba.tools.saroo_capture_import D:\
```

The mounted card remains read-only during ingestion.
