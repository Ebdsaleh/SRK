# SAROO in-game capture checkpoint

SRK's first real-hardware menu captures proved that the Saturn-side helper can
copy Work RAM through SAROO's SD-file path and recover the result on the host.
The next checkpoint is deliberately narrower than a general debugger: prove one
**title-neutral execution-triggered WRAM-H capture** while a game is entering its
first-read program.

## Why this checkpoint uses the IP first-read address

The Sega Saturn System ID/IP header stores the first-read transfer destination at
offset `0xF0`. During boot, the boot system transfers the first file from the CD
filesystem to that address. The field is therefore available generically for any
proper Saturn disc and avoids putting a commercial-title-specific program counter
into SRK.

Important distinction: the boot specification defines a **transfer address**.
It does not promise that every title directly executes that address. SRK therefore
calls this a *first-read execution checkpoint*, not a universal game-entry hook.
If execution never reaches the address, no capture should be produced.

## Separate generated tree

The source for this stage is the already built and hardware-validated controller
capture-menu tree:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-CAPTURE
```

Prepare a new tree instead of editing it in place:

```bat
python -m rikai_kotoba.tools.saroo_ingame_entry_prepare ^
  "C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-CAPTURE" ^
  "C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-INGAME-FIRSTREAD"
```

The output adds one menu action:

```text
SRK Arm 1st-Read Capture
```

The preparation step leaves the source tree unchanged and refuses to overwrite
an existing output directory.

## Runtime behavior

Arming the menu action does not immediately write a dump. During game loading,
SRK reads the big-endian first-read address from the in-memory IP header at:

```text
0x06002000 + 0xF0
```

The address must be:

- inside Saturn WRAM-H;
- at or above `0x06002000`;
- below `0x06100000`;
- SH-2 instruction aligned.

If valid, SRK assigns the existing SAROO `game_break_pc` / `game_break_handle`
mechanism. Upstream SAROO's game-loading path already installs the SH-2 UBR
breakpoint whenever `game_break_pc` is non-zero.

If the breakpoint is reached, the SRK handler is **one-shot**. It disables the
UBR breakpoint and clears the handler state before performing SD I/O, then writes:

```text
/SAROO/SRK_GAME_WRAMH.BIN
```

Expected size:

```text
1048576 bytes
```

The captured range is:

```text
0x06000000-0x060FFFFF
```

Because the UBR handler runs in the paused title's execution context, a small
portion of the dump may include stack/debug-handler effects. The checkpoint is
intended first to prove that an execution-triggered original-hardware capture is
possible and that execution can return afterward.

## Build gate

After preparing the new tree, build it with the already validated Python-native
SRK SAROO builder:

```bat
srk build-saroo-firmware ^
  "C:\Users\Developer.ERIDU\Saturn-Dev\SAROO-SRK-INGAME-FIRSTREAD" ^
  --toolchain-root "C:\Users\Developer.ERIDU\Saturn-Dev\SaturnOrbit"
```

Do not deploy that firmware merely because it builds. Record the exact candidate
`ssfirm.bin` size and SHA-256 first, preserve the currently accepted capture-menu
firmware, then use SRK's guarded accepted-firmware transition path.

## Mutation scope

The in-game capture file is a known SRK research output:

```text
SAROO/SRK_GAME_WRAMH.BIN
```

Future firmware transitions may tolerate that exact path when present only if it
is an ordinary 1 MiB file. Games, configuration, MCU/FPGA firmware, and every
other unrelated card path remain protected by the original whole-card manifest.

## Public/core neutrality

No commercial-title-specific breakpoint address is embedded in this checkpoint.
The first-read address is taken from the disc's own standard Saturn IP header.
Later arbitrary-PC capture support must likewise accept the PC as caller-supplied
research data rather than hard-coding a game address into reusable SRK code.
