# SAROO Runtime Menu

SRK's runtime-menu work is intentionally staged so controller observation,
menu-state logic, video takeover, memory capture, and SD I/O can each be
validated independently on real Sega Saturn hardware.

## 2026-10-08 — physical acceptance of the inert runtime input hook

The first runtime tranche only observes controller data already collected by
SAROO's existing BIOS controller hook. SRK does not issue its own SMPC command
for this path.

Activation is title-neutral:

```text
hold Saturn L + R
  -> 50 consecutive completed controller samples
  -> SRK_RUNTIME_INPUT_OPEN_MENU
  -> internal request latch
```

The corresponding hardware candidate was:

```text
ssfirm.bin
size:    484246 bytes
SHA-256: f8b837858ed4d5365164ee3439a05627d2981f42578e00c47c5580530e257830
```

Before physical testing, guarded deployment reported matching pre- and
post-transition card inventories. Independent read-only inspection confirmed the
installed firmware hash and a second card guard reported `MATCH`.

The candidate was then tested on original Saturn hardware with a commercial
title. The title booted normally, controller input remained normal, L+R was held
for the activation interval several times, both shoulders were released between
activations, and extended gameplay remained stable. No crash, hang, reset,
graphical corruption, audio fault, or stuck controller state was observed.

This establishes a physical checkpoint for **runtime controller observation and
activation detection only**. It does not establish a visible overlay, paused
runtime menu, capture action, or recording feature.

The inert hook performs no new SD write, RAM capture, direct SMPC polling, or VDP
configuration change.

## Existing research-output files after the inert-hook test

The inert hook does not create capture files. Existing SRK outputs can therefore
remain on the card unchanged across this test. Their presence must not be
interpreted as a new runtime-menu capture.

## Renderer safety requirement

Upstream SAROO's `conio_init()` is not suitable as an in-game overlay initializer.
It calls `vdp_init()`, which reconfigures VDP1/VDP2 state, clears VDP2 VRAM, and
rewrites color RAM. Calling it over a running title would destroy title-owned
video state.

SRK's runtime renderer must therefore be explicitly non-destructive. Before any
visible hardware test, the implementation must define exactly which VDP
registers and memory ranges it touches, preserve those resources, and restore
them before returning control to the title.

The preferred architecture is a modal runtime menu entered from the already
validated controller hook:

```text
running title
  -> completed controller sample
  -> L+R activation detector
  -> runtime-menu state requests entry
  -> preserve required machine/video state
  -> render minimal SRK menu
  -> service menu input through the existing BIOS controller path
  -> dismiss/resume
  -> restore preserved state
  -> return to title
```

The first text menu must contain **Resume only**. Capture and recording commands
remain later checkpoints.

## Read-only VDP2 preservation checkpoint

Before SRK writes any video register, the generated R3 firmware snapshots only
the VDP2 color-offset register family into firmware-owned state when the runtime
menu opens:

```text
CLOFEN
CLOFSL
COAR
COAG
COAB
COBR
COBG
COBB
```

These are the exact resources reserved for the first low-impact visual work. The
snapshot stage itself is deliberately read-only: it does not write those
registers, VDP1 state, VDP2 VRAM, or VDP2 CRAM.

The R3 read-only snapshot tree built successfully through the real SH-ELF
firmware toolchain with 20 objects and clean/build exit code 0. Its generated
`ssfirm.bin` remained the standard 484246 bytes and had SHA-256:

```text
ba1c1f2ef33ec15cecb0b32a61c84ac07bd062e0d9affe78e3d80be3cc28d682
```

R3 was not deployed to the SAROO SD card.

## Bounded visible canary checkpoint

R4 introduced a separate `srk_runtime_video_canary` helper rather than adding
write behavior to the read-only snapshot helper.

On a validated runtime-menu OPENED event R4:

```text
captures CLOFEN/CLOFSL/COA*/COB*
  -> enables the seven VDP2 color-offset targets
  -> leaves CLOFSL unchanged
  -> programs both A and B offset banks to the same red offset
  -> holds that canary for three display frames
  -> restores the exact captured color-offset register set
  -> returns to the title path
```

The R4 firmware was guarded onto the real SAROO card and independently verified.
On physical Saturn hardware the commercial title remained completely stable, but
the three-frame red pulse was not perceptible to the user. This is therefore a
useful stability result but not sufficient visual proof that the canary was seen.

R4 intentionally owns no VDP2 VRAM, CRAM, tile-map, character-data, or VDP1
resource. It performs no SD write, RAM capture, or direct SMPC poll.

## Modal red-shell checkpoint

R5 changes the experiment from a fixed three-frame pulse to the lifecycle shape
needed by the eventual menu.

The R5 generator starts from the validated R4 tree and creates a new tree. On the
first release-gated L+R activation it:

```text
captures the exact VDP2 color-offset state
  -> forces all seven color-offset targets to solid red
  -> keeps the title's main path blocked inside the existing controller hook
  -> calls the original BIOS controller routine once per display frame
  -> waits for both shoulders to be released
  -> accepts a second 50-sample L+R hold as dismissal
  -> restores the exact captured VDP2 color-offset register set
  -> returns to the title
```

The solid-red surface uses signed 9-bit VDP2 offsets: red `+255` and green/blue
`-255`, with both A/B offset banks programmed identically. It still owns no
VRAM, CRAM, VDP1, SD-card, or capture resource.

Keeping the title's main path inside the hook is important. Allowing normal title
execution to continue beneath a persistent overlay could let the title change
video state after SRK captured it, making a later restore stale. The modal proof
therefore tests the stronger save/take-over/service-input/restore/return model.

The original BIOS controller routine is the only controller-refresh operation
used while modal; SRK still issues no direct SMPC command. Because repeated BIOS
controller refresh while the title path is blocked is new behavior, R5 includes
a first-test fail-safe: if no dismissal is observed, it restores automatically
after 600 display frames (about 10 seconds at 60 Hz or 12 seconds at 50 Hz).

R5 is still not the final text menu. Its purpose is to validate the modal
lifecycle and exact restoration with an unmistakable visible surface before SRK
claims VRAM/CRAM resources for text rendering.

## Planned validation order

1. Runtime-menu state machine, independent of video hardware.
2. Exact VDP/resource preservation contract.
3. Read-only VDP2 preservation snapshot.
4. Bounded visible color-offset canary with exact restore.
5. Modal solid-color shell: L+R open, L+R dismiss, exact restore.
6. Minimal text shell with `SRK` / `Resume` only.
7. Physical text-menu enter/resume validation on real hardware.
8. `Capture Both`.
9. Individual WRAM-H / WRAM-L captures.
10. Mark / metadata.
11. Bounded recording controls.

Each stage must remain title-neutral in public SRK code and should be promoted
only after the preceding stage has been physically accepted where hardware is
involved.
