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
  -> Resume
  -> restore preserved state
  -> return to title
```

The first visible menu must contain **Resume only**. Capture and recording
commands remain later checkpoints.

## Planned validation order

1. Runtime-menu state machine, independent of video hardware.
2. Exact VDP/resource preservation contract.
3. Minimal visible shell with `Resume` only.
4. Physical enter/resume validation on real hardware.
5. `Capture Both`.
6. Individual WRAM-H / WRAM-L captures.
7. Mark / metadata.
8. Bounded recording controls.

Each stage must remain title-neutral in public SRK code and should be promoted
only after the preceding stage has been physically accepted where hardware is
involved.
