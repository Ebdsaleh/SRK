# SAROO Real-Hardware Work RAM Capture

This document records SRK's first physically validated Sega Saturn Work RAM
capture path using a SAROO cartridge and controller-accessible SRK firmware menu.

## Hardware checkpoint — 2026-10-07

The capture-menu firmware had already passed a guarded firmware transition and
booted successfully on the user's real Sega Saturn. The normal SAROO menu and
game library remained functional.

The firmware exposed two title-neutral menu actions:

```text
SRK Capture WRAM-L
SRK Capture WRAM-H
```

Each action writes exactly 1 MiB using the 64 KiB chunked SAROO file-write path.

### Work RAM-L

Output:

```text
/SAROO/SRK_WRAML.BIN
```

Observed size:

```text
1048576 bytes
```

Observed SHA-256:

```text
30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58
```

The menu-stage WRAM-L capture was entirely zero-filled. This is a valid physical
capture result at that checkpoint and should not be interpreted as a failed file
write.

Canonical mapped range:

```text
0x00200000-0x002FFFFF
```

### Work RAM-H

Output:

```text
/SAROO/SRK_WRAMH.BIN
```

Observed size:

```text
1048576 bytes
```

Observed SHA-256:

```text
a546912eb7eb1b16f4ea45e3074f795c3be6085af1a9ac095164ce4dc900f04c
```

The real file contained **17,475 non-zero bytes**. The final non-zero byte was at
dump offset `0x5FFF`, corresponding to Saturn address `0x06005FFF`; all later
bytes in this menu-stage 1 MiB snapshot were zero.

Canonical mapped range:

```text
0x06000000-0x060FFFFF
```

The captured WRAM-H bytes included recognizable Saturn/SAROO boot structures,
including `SEGA SEGASATURN` identification data and `SAROO firm` text. This is
strong physical evidence that the dump contains live Saturn memory rather than
only a mechanically correct empty output file.

## Proven hardware path

The physical checkpoint proves:

```text
real Sega Saturn Work RAM
  -> SRK Saturn-side capture helper
  -> SAROO write_file path
  -> SD-card raw capture file
  -> host-readable exact 1 MiB artifact
```

It does not yet prove an in-game checkpoint. Both captures above were initiated
from the SAROO boot menu.

## Host-side ingestion

SRK can now import both raw card files into its immutable CaptureStore evidence
format without modifying the mounted card:

```bat
python -m rikai_kotoba.tools.saroo_capture_import ^
  D:\ ^
  --checkpoint saroo-menu ^
  --session-label first-real-saturn-capture
```

The command validates the exact 1 MiB size of both files, records their canonical
Saturn address ranges and SHA-256 values, reports zero/non-zero distribution, and
publishes one verified off-card capture artifact under the normal SAROO dump
workspace.

The source SD-card files are read-only inputs and remain untouched.

## Research-output mutation boundary

After capture validation, the two known SRK research files are:

```text
SAROO/SRK_WRAML.BIN
SAROO/SRK_WRAMH.BIN
```

Future guarded firmware transitions may permit these exact paths to differ from
the original card baseline, but only when each present file is an ordinary file
of exactly 1 MiB. All other unrelated card content remains protected by the
original whole-card manifest.

This keeps generated research evidence separate from the protected game library,
configuration, MCU/FPGA firmware, and all unrelated files.
