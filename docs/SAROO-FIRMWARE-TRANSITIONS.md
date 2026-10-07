# Guarded SAROO research-firmware transitions

SRK treats the first successful whole-card-guarded SAROO deployment differently
from later research-firmware revisions.

The original whole-card manifest remains the authority for every card path other
than:

```text
SAROO/ssfirm.bin
```

Once the first accepted SRK firmware is installed, that one file is expected to
differ from the original card baseline.  Later transitions therefore permit
that single pre-existing difference while requiring the exact currently
accepted firmware SHA-256 as an additional gate.

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

## Next controller-capture candidate

The separate generated tree:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-CAPTURE
```

was physically prepared and built on ERIDU without modifying the accepted
`SAROO-SRK` generated tree.

Validation before build:

```text
237 unittest tests passed
237 pytest tests passed
23 pytest subtests passed
```

Build result:

```text
17 Firm_Saturn objects compiled
clean exit: 0
build exit: 0
result: SUCCESS
```

Artifacts:

```text
ssfirm.elf
  90224 bytes
  SHA-256 965ed602fa1fd59485302f74b9e9a4b81b963b97f53ee1e0ad7a28ab0c46515b

ssfirm.bin
  484246 bytes
  SHA-256 28c154b415b570d1d3075fbe5fa5cd1bb51ab5ef511fe9a0318f43c97c783d95

dump.txt
  843717 bytes
  SHA-256 0febbfdd9b1d5a65288e8558182d2cc8699140b11e7c13ba9c9bd5102150796c
```

The candidate adds controller-accessible boot-menu actions for Work RAM capture.
It has not yet been physically installed or capture-tested.

## Transition safety contract

`transition_saroo_firmware_guarded()` requires:

1. the original reviewed off-card whole-card guard manifest;
2. the exact reviewed manifest SHA-256;
3. the exact SHA-256 of the currently accepted firmware;
4. the exact SHA-256 of the candidate firmware;
5. a backup root outside the card;
6. every unrelated card path to match the original baseline.

The transition then:

1. verifies the card against the original manifest while allowing only
   `SAROO/ssfirm.bin` to differ;
2. verifies that the live `ssfirm.bin` hash exactly matches the accepted current
   firmware hash;
3. creates or reuses a content-addressed verified off-card backup of the current
   firmware;
4. stages and verifies the candidate beside the live destination;
5. re-checks the live current firmware immediately before replacement;
6. replaces only `SAROO/ssfirm.bin`;
7. verifies the installed candidate SHA-256;
8. verifies the whole card again while permitting only `SAROO/ssfirm.bin` to
   differ from the original baseline.

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
the original whole-card manifest is no longer an exact byte-for-byte firmware
baseline after the first accepted deployment.

## Capture files are separate mutations

The controller capture actions create:

```text
/SAROO/SRK_WRAML.BIN
/SAROO/SRK_WRAMH.BIN
```

Those files are **not** authorised by the firmware-transition guard. This is
intentional. Firmware revision and runtime capture are separate mutation scopes
and should be validated separately.
