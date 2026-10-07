# SAROO Hardware Validation

This document records physical validation checkpoints for SRK's title-neutral
SAROO integration. It deliberately separates file/build success from behavior on
real Sega Saturn hardware.

## 2026-10-07 — first guarded Saturn-side firmware deployment

The existing SAROO SD card was independently prepared before SRK and contains a
large working game library. SRK therefore treated the card and its original
Saturn-side firmware as preserve-first evidence.

Before the first write, the card baseline was recorded as:

```text
Files           : 1555
Directories     : 127
Total file bytes: 60569378580 bytes (56.41 GiB)
Files SHA-256ed : 149
Manifest SHA-256: d9a2f25460622dec04466af349e8bbec12c300bf697ada6f349ccfb25db9f333
```

Original working `SAROO/ssfirm.bin`:

```text
size:    447357 bytes
SHA-256: d93c2c91e958a3bfd125fbf02cccea729ddc8c6f1e1bd9bed298389614880ba7
```

A verified off-card copy was created before replacement.

The first SRK candidate installed on the card was:

```text
size:    484246 bytes
SHA-256: 7f30e1a58ff1a26cd70af1d36a85129fad132016b2b7c47626e3c2fb04a90686
```

The guarded apply reported:

```text
Pre-write guard  : MATCH
Post-write guard : MATCH (only SAROO/ssfirm.bin authorised to differ)
```

An independent read-only inspection then confirmed the candidate size/hash and
presence of the normal SAROO directory, `mcuapp.bin`, `saroocfg.txt`, ISO
directory, and update directory. A second whole-card verification again matched
when only `SAROO/ssfirm.bin` was permitted to differ.

### Real hardware acceptance

The card was safely ejected, returned to the SAROO cartridge, and booted on the
user's real Sega Saturn.

User physically confirmed:

- SAROO booted normally;
- the existing game library remained intact;
- games remained functional.

This established the first physically accepted Saturn-side SRK firmware
checkpoint.

## 2026-10-07 — controller capture firmware

A second generated tree was prepared outside the accepted source tree and built
with the existing SRK capture helper plus two controller-accessible menu actions:

```text
SRK Capture WRAM-L
SRK Capture WRAM-H
```

Candidate `ssfirm.bin`:

```text
size:    484246 bytes
SHA-256: 28c154b415b570d1d3075fbe5fa5cd1bb51ab5ef511fe9a0318f43c97c783d95
```

Before transition, the first accepted SRK firmware was independently backed up
and verified off-card. The guarded firmware-to-firmware transition then reported
matching pre- and post-transition card guards, and an independent inspection
confirmed the new candidate hash.

The card was booted on the real Saturn. Both new SRK capture menu entries were
visibly present alongside the normal SAROO menu.

## 2026-10-07 — first physical Work RAM captures

The user physically invoked both controller-accessible capture actions on the
real Saturn.

### WRAM-L

```text
/SAROO/SRK_WRAML.BIN
size:    1048576 bytes
SHA-256: 30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58
range:   0x00200000-0x002FFFFF
```

The captured payload was entirely zero-filled at the SAROO boot-menu checkpoint.
The exact 1 MiB output proves the low-memory capture action and chunked SD write
completed; the zero content is a property of that checkpoint, not evidence of a
short file.

### WRAM-H

```text
/SAROO/SRK_WRAMH.BIN
size:    1048576 bytes
SHA-256: a546912eb7eb1b16f4ea45e3074f795c3be6085af1a9ac095164ce4dc900f04c
range:   0x06000000-0x060FFFFF
```

The WRAM-H dump contained 17,475 non-zero bytes. The last non-zero byte occurred
at offset `0x5FFF` (`0x06005FFF`). Recognizable Saturn/SAROO boot structures were
present in the payload, including `SEGA SEGASATURN` identification data and
`SAROO firm` text.

This is the first physical proof that SRK can capture live Sega Saturn memory on
original hardware and return it as a host-readable artifact through SAROO.

The proven path is:

```text
real Sega Saturn Work RAM
  -> SRK capture helper
  -> SAROO file-write path
  -> SD card
  -> host-readable 1 MiB dump
```

These captures were taken from the SAROO boot menu. In-game capture remains a
separate future checkpoint and must not be inferred from this validation.

See `SAROO-HARDWARE-CAPTURE.md` for the host-side ingestion and research-output
guard policy built on top of this physical checkpoint.
