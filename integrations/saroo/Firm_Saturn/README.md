# SRK SAROO `Firm_Saturn` capture helper

This directory contains **SRK-authored, title-neutral integration code** for the
Saturn-side firmware in the upstream SAROO project.  It does not contain a copy
of SAROO firmware source.

The first integration target was researched against upstream SAROO commit:

```text
c31bf6192eff59533d7268dfdf6c791f11a1f7c9
```

Upstream repository:

```text
https://github.com/tpunix/SAROO
```

## Why this helper exists

SAROO's upstream Saturn firmware already exposes:

```c
int write_file(char *name, int offset, int size, void *buf);
```

The MCU-side `SSCMD_FILEWR` handler supports two useful behaviors:

- `offset == -1` creates/truncates a file and writes from offset zero;
- a non-negative offset opens the file and writes at that explicit position.

Upstream `sci_shell.c` also contains an `fwt` diagnostic that writes `0x10000`
(64 KiB) of Saturn memory through `write_file()`.  SRK therefore treats 64 KiB
as the **currently verified staging-write size** instead of assuming that a
1 MiB Work RAM region can safely be handed to the shared staging buffer in one
operation.

`srk_capture_helper.c` writes a requested range as deterministic 64 KiB chunks:

```text
first chunk  -> write_file(path, -1,       0x10000, address + 0x00000)
second chunk -> write_file(path, 0x10000,  0x10000, address + 0x10000)
...
```

A canonical 1 MiB Work RAM capture therefore uses sixteen writes.

## What the helper does *not* decide

The helper deliberately does not choose how a capture is triggered.  That is a
separate policy layer.  A future integration may use a debug-shell command,
breakpoint/debug hook, controller hotkey, or another mechanism that has been
verified against the user's actual SAROO firmware.

Keeping trigger policy separate means the capture file and PC import workflow do
not have to change when the trigger mechanism improves.

## Current helper API

```c
int srk_capture_range_to_file(
    char *path,
    unsigned int start_address,
    unsigned int size
);

int srk_capture_work_ram_low(char *path);
int srk_capture_work_ram_high(char *path);
```

The Work RAM wrappers use the title-neutral Saturn regions currently modeled by
SRK:

```text
Work RAM-L  0x00200000 - 0x002FFFFF  (1 MiB)
Work RAM-H  0x06000000 - 0x060FFFFF  (1 MiB)
```

## Minimal upstream integration for development

This is a development integration, not a claim that stock SAROO firmware already
ships SRK commands.

1. Use a local SAROO checkout that you are prepared to rebuild.
2. Copy `srk_capture_helper.c` and `srk_capture_helper.h` into its
   `Firm_Saturn/` directory.
3. Add `obj/srk_capture_helper.o` to the `OBJ` list in SAROO's
   `Firm_Saturn/Makefile`.
4. Include `srk_capture_helper.h` from the Saturn-side command/debug source that
   will trigger captures.
5. Trigger one of the helper functions with a path that already has a valid
   parent directory on the SAROO SD card.  The upstream README documents
   `/SAROO/` as a normal SD-card directory, so development captures can use
   names such as `/SAROO/SRK_WRAML.BIN` and `/SAROO/SRK_WRAMH.BIN` without
   requiring directory creation support.

For an upstream `sci_shell.c` development build, conceptually the command bodies
can be as small as:

```c
CMD(srkwl) {
    int retv = srk_capture_work_ram_low("/SAROO/SRK_WRAML.BIN");
    printk("SRK WRAM-L capture: %d\n", retv);
}
CMD(srkwh) {
    int retv = srk_capture_work_ram_high("/SAROO/SRK_WRAMH.BIN");
    printk("SRK WRAM-H capture: %d\n", retv);
}
```

Do not add these commands blindly to a different SAROO revision.  Confirm the
relevant command dispatcher and `write_file()` contract first.

## PC-side import

After a raw dump is copied from the SAROO SD card to the PC, import it into an
immutable SRK capture artifact:

```text
srk import-saroo-dump SRK_WRAMH.BIN \
    --base-address 0x06000000 \
    --expected-size 0x100000 \
    --checkpoint title-screen \
    --label work_ram_high
```

Unless `--capture-root` is supplied, the verified artifact is written beneath:

```text
SRK-Workspace/Dumps/SAROO/
```

The original raw SD dump is never modified.  SRK creates a new capture directory
containing the region bytes plus `capture.json` with addresses, sizes, timestamp,
and SHA-256 integrity metadata.

## Licensing boundary

The files in this directory are SRK-authored integration code.  Upstream SAROO
`Firm_Saturn` source files identify their own licensing terms in their headers.
If you redistribute a modified SAROO firmware build, review and comply with the
upstream project's applicable license terms.
