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

This establishes the installed SRK candidate as the first physically accepted
Saturn-side research firmware checkpoint. It does **not** yet validate the SRK
memory-capture commands themselves.

## Next capture-access checkpoint

The initial SRK integration exposes `srkwl` and `srkwh` through SAROO's serial
debug shell. Upstream SAROO also exposes the serial debug tool from its normal
boot menu, but SRK should not require extra serial hardware merely to validate
the capture helper.

SRK therefore provides a second-stage generator that starts from the already
validated `SAROO-SRK` generated tree and creates a new tree, leaving both the
upstream source and hardware-validated generated tree unchanged.

The second tree adds two explicit boot-menu actions:

```text
SRK Capture WRAM-L -> /SAROO/SRK_WRAML.BIN
SRK Capture WRAM-H -> /SAROO/SRK_WRAMH.BIN
```

Both use the same existing title-neutral 64 KiB chunked helper and each produces
a 1 MiB raw Work RAM capture.

The first controller-accessible capture test should be performed from the SAROO
menu before attempting in-game capture policy. A menu capture validates the
helper, file-write path, and resulting artifact without yet claiming that a game
runtime checkpoint can be captured.
