# SAROO first title-neutral in-game checkpoint

SRK's controller-accessible boot-menu capture path has been physically validated
on a real Sega Saturn.  The next stage is deliberately narrow: prove that the
same capture helper can run while title code is executing, without introducing
a game-specific breakpoint into the public repository.

## Why the 1st-read address

The Saturn System ID/IP header contains a 32-bit **1st-read address** at offset
`0xF0`.  SAROO keeps the IP header in WRAM-H beginning at `0x06002000`, so the
field is available at:

```text
0x060020F0
```

The field is big-endian and is read with upstream SAROO's existing `BE32()`
helper.

The Saturn boot specification defines this field as the transfer destination for
the 1st-read file.  Loading the file does **not** guarantee automatic execution.
Therefore SRK does not call this a universal game-entry address.  Instead, the
first generic experiment arms an execution breakpoint at the field's value and
captures only if the title's Application Initial Program later transfers control
to that address.

This distinction matters: a title that does not execute its 1st-read destination
will simply produce no in-game capture.  That is evidence, not a reason to guess
a different address.

## Separate generated tree

The hardware-validated controller capture tree remains untouched:

```text
SAROO-SRK-CAPTURE
```

SRK creates a new tree for this experiment, for example:

```text
SAROO-SRK-INGAME-FIRSTREAD
```

The preparation layer refuses to overwrite an existing output and refuses to
place output inside the source generated tree.

## New menu action

The generated firmware adds:

```text
SRK Arm 1st-Read Capture
```

Selecting this item only arms a one-shot request.  It does not write a dump from
the menu.

When the next game is loaded, SRK reads the big-endian 1st-read address from
`0x060020F0`.  The address must be:

- even (SH-2 instruction aligned);
- at or above `0x06002000`;
- below `0x06100000`.

Invalid values cancel the arm operation rather than installing an unknown UBR
breakpoint.

## Existing SAROO UBR path

SRK reuses upstream SAROO's existing in-game SH-2 UBR path rather than adding a
second exception mechanism.

Upstream `game_load.c` already installs a UBR execution breakpoint whenever
`game_break_pc` is non-zero.  Upstream `ubr_debug.c` dispatches the registered
handler when the exception PC equals `game_break_pc + 2`, then the assembly
exception wrapper restores the saved SH-2 state and executes `rte`.

SRK only supplies the breakpoint address and handler before that existing block.

## One-shot handler

When the first-read address is reached, the SRK handler:

1. disables the UBR execution breakpoint;
2. clears `game_break_pc`;
3. clears the registered game-break handler;
4. clears its own armed flag;
5. captures canonical WRAM-H using the already hardware-validated 64 KiB chunked
   SAROO file-write path;
6. returns to upstream SAROO's exception wrapper, which resumes title execution.

Output:

```text
/SAROO/SRK_GAME_WRAMH.BIN
```

Expected size:

```text
1048576 bytes
```

The raw file is deliberately distinct from the boot-menu `SRK_WRAMH.BIN`, so a
new file is positive evidence that the in-game handler actually ran.

## Debug-context caveat

The UBR exception entry saves registers on the title's current stack before the
C handler runs.  Therefore a small portion of the resulting WRAM-H snapshot may
reflect the paused exception/debug context rather than the exact bytes present
one instruction earlier.  This is expected and must be preserved as part of the
capture provenance.

A later stage should persist the saved register frame as explicit metadata so
analysis can distinguish debugger-induced stack bytes from title state.

## Safety boundary

This stage does not:

- modify game images;
- patch a title executable;
- hardcode a Soul Hackers address;
- modify MCU or FPGA firmware;
- add an automatic repeated breakpoint loop;
- claim that every Saturn title executes its 1st-read address.

The first experiment is one-shot and early.  Once physically validated, SRK can
add a caller-supplied PC profile for useful later runtime checkpoints while
keeping game-specific addresses outside the public reusable core.

## Research-output guard

The guarded research-firmware transition layer recognizes these exact SRK raw
capture paths, when present, only if each is an ordinary 1 MiB file:

```text
SAROO/SRK_WRAML.BIN
SAROO/SRK_WRAMH.BIN
SAROO/SRK_GAME_WRAMH.BIN
```

Every unrelated card path remains governed by the original whole-card baseline.
Firmware transitions still modify only `SAROO/ssfirm.bin`.
