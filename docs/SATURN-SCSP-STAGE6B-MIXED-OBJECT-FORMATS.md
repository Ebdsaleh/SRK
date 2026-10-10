# Saturn SCSP Stage 6B — mixed ELF/COFF link finding

## Status

Stage 6B Gate 2 reached the final link after every SRK C source compiled and the
startup source assembled successfully.  The link stopped on the installed
`SEGA_CDC.A` with:

```text
could not read symbols: File format is ambiguous
```

No ISO or SAROO/card write occurred.

## Mjolnir evidence

The read-only Mjolnir archive inspector established that all three reviewed SBL
libraries use a normal classic Unix `ar` container, but their member object
formats differ.

### `sega_gfs.a`

- classic Unix `ar`;
- 7 payload members;
- every payload begins with ELF magic;
- every payload decodes as ELF32, big-endian, relocatable, machine SH (42).

### `SEGA_CDC.A`

- classic Unix `ar`;
- 17 payload members;
- payload members do **not** begin with ELF magic;
- every payload begins with `05 00` and has a structurally consistent 20-byte
  Hitachi SH COFF file header.

### `SEGADGFS.A`

- classic Unix `ar`;
- 12 payload members;
- the same `05 00` member signature is present throughout;
- this is therefore part of the COFF side of the historical SBL distribution,
  not a replacement ELF CDC dependency.

The important boundary is therefore:

```text
sega_gfs.a  -> ELF32 SH objects
SEGA_CDC.A  -> Hitachi SH big-endian COFF objects
```

The archive wrapper itself is not malformed and does not need repacking.

## Format identification

SRK now has a minimal raw-byte COFF header decoder.  For Hitachi SuperH:

```text
0x0500 -> big-endian SH COFF
0x0550 -> little-endian SH COFF
```

The observed CDC members use the big-endian `0x0500` form.

This explains why merely passing `SEGA_CDC.A` to an SH-ELF linker can be
ambiguous: the linker must be told which historical SH COFF BFD target is meant.
Saturn GNU build practice uses the normal `coff-sh` target for Sega's COFF
libraries.

## Safe next gate

Do **not** modify the normal standalone builder yet.

A bounded off-card link probe now exists:

```text
python -m rikai_kotoba.tools.saturn_stage6b_link_probe --project <fresh-project>
```

It first proves:

- GFS archive payloads are ELF32 big-endian SH relocatables;
- CDC archive payloads are Hitachi SH big-endian COFF;
- generated project inputs and private dependencies still match their pinned
  provenance.

Only then does it compile/assemble in a dedicated probe directory and link with
this narrowly scoped input-format sequence:

```text
... SRK ELF objects ...
sega_gfs.a
--format=coff-sh
SEGA_CDC.A
--format=elf32-sh
-lgcc
```

The probe never invokes the ISO builder and has no SAROO/card path.

If this link succeeds with the real historical toolchain, the exact format
handling can be promoted into the normal Python-native builder and then the
complete Stage 6B off-card build gate can be rerun from another fresh project.

If it fails, preserve the probe project unchanged and use the exact linker
output as the next piece of evidence.
