# SAROO Runtime Menu

SRK's runtime-menu work is intentionally staged so controller observation,
post-launch execution, menu-state logic, video takeover, memory capture, and SD
I/O can each be validated independently on real Sega Saturn hardware.

## 2026-10-08 — runtime-hook physical non-regression checkpoint

The first runtime tranche observes controller data at SAROO's existing BIOS key
hook. SRK does not issue its own SMPC command for this path.

The intended activation is title-neutral:

```text
hold Saturn L + R
  -> 50 consecutive samples
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
several times, and extended gameplay remained stable. No crash, hang, reset,
graphical corruption, audio fault, or stuck controller state was observed.

This is a **non-regression checkpoint only**. Because that firmware had no
observable activation marker, the hardware run did not prove that the L+R
request latch fired, nor that `cdp_hook` continued to be invoked throughout
normal gameplay. Later evidence requires those earlier claims to remain narrow.

The inert hook performs no new SD write, RAM capture, direct SMPC polling, or VDP
configuration change.

## What post-launch presence is actually established

SAROO's Saturn firmware linker script places the firmware image at `0x02000000`,
outside Saturn Work RAM. Upstream SAROO also treats bus addresses in
`0x02000000-0x02FFFFFF` as a region directly accessible by both the Saturn side
and the cartridge MCU. This supports the architectural expectation that SRK
firmware code is cartridge-resident rather than copied into the title's 1 MiB
WRAM-H image.

Separately, SRK's hardware-validated 1st-read UBR capture proved that an SRK
handler can execute after a title begins execution: the UBR handler ran at the
configured title entry event, wrote a 1 MiB WRAM-H snapshot, disarmed, and
returned to the title.

Those facts do **not** prove continuous or recurring SRK execution while normal
gameplay proceeds. That is now treated as a separate hardware milestone.

## Controller-sample caveat

The original runtime-hook integration samples the BIOS controller memory at
`0x06020232` before invoking SAROO's original BIOS routine. The exact freshness
and recurrence semantics of that memory location during arbitrary commercial
gameplay have not been physically established.

During later testing, holding L+R in the SAROO menu could also be interpreted by
the menu as repeated actions. That menu uses its own edge/state logic and is not
identical to the in-game 16-bit sample path, so the behavior does not by itself
explain the in-game failure. It does, however, reinforce the requirement that
SRK stop treating passive controller observation as proof of a reliable runtime
callback.

## Existing research-output files after runtime-hook tests

The inert hook does not create capture files. Existing SRK outputs can therefore
remain on the card unchanged across these tests. Their presence must not be
interpreted as a new runtime-menu capture.

## Renderer safety requirement

Upstream SAROO's `conio_init()` is not suitable as an in-game overlay initializer.
It calls `vdp_init()`, which reconfigures VDP1/VDP2 state, clears VDP2 VRAM, and
rewrites color RAM. Calling it over a running title would destroy title-owned
video state.

SRK's eventual runtime renderer must therefore be explicitly non-destructive.
Before any visible hardware test, the implementation must define exactly which
VDP registers and memory ranges it touches, preserve those resources, and
restore them before returning control to the title.

## Read-only VDP2 preservation checkpoint

R3 snapshots only the VDP2 color-offset register family into firmware-owned
state when the runtime-menu lifecycle opens:

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

The snapshot stage itself is deliberately read-only: it does not write those
registers, VDP1 state, VDP2 VRAM, or VDP2 CRAM.

The R3 tree built successfully through the real SH-ELF firmware toolchain with
20 objects and clean/build exit code 0. Its `ssfirm.bin` remained 484246 bytes
with SHA-256:

```text
ba1c1f2ef33ec15cecb0b32a61c84ac07bd062e0d9affe78e3d80be3cc28d682
```

R3 was not deployed.

## Bounded visible canary checkpoint

R4 introduced a separate `srk_runtime_video_canary` helper. On the intended
runtime-menu OPENED event it captures the color-offset register set, applies a
red offset for three display frames, restores the exact values, and returns.

The R4 firmware was guarded onto the real SAROO card and independently verified.
On physical Saturn hardware the commercial title remained completely stable, but
the three-frame red pulse was not perceptible. This is a useful stability result,
not visual proof that the runtime activation occurred.

R4 intentionally owns no VDP2 VRAM, CRAM, tile-map, character-data, or VDP1
resource. It performs no SD write, RAM capture, or direct SMPC poll.

## Modal red-shell checkpoint and result

R5 attempted the stronger lifecycle required by the eventual menu:

```text
L+R request
  -> capture exact VDP2 color-offset state
  -> solid-red modal ownership
  -> keep title main path inside the controller hook
  -> refresh BIOS controller data while modal
  -> second release-gated L+R hold dismisses
  -> exact restore
  -> return to title
```

R5 built successfully, was installed through the guarded transition workflow,
and its card hash was independently verified. The commercial title continued to
play normally, but no red modal surface appeared. Trying the same L+R gesture in
the SAROO menu also did not provide a trustworthy held-input proof.

R5 is therefore **not physically accepted as a modal runtime menu**. The failure
is now treated primarily as an observability/callback problem rather than a
renderer problem. SRK must first prove that a recurring callback is still
reaching SRK after the title has crossed its entry point.

## Armed post-entry execution proof (R6)

R6 deliberately removes controller input from the question.

The user explicitly arms `SRK Arm Runtime Proof` in the SAROO menu before
launching a title. At game-load time SRK installs the already proven title-neutral
IP.BIN 1st-read UBR gate. The UBR handler performs no capture and no SD I/O; it
only marks that the title crossed its entry point and disarms itself.

Only after that entry marker has fired does SRK count later invocations of the
existing SAROO `cdp_hook`:

```text
arm in SAROO menu
  -> launch title
  -> dynamic IP.BIN 1st-read UBR fires once
  -> entry_seen = true
  -> later cdp_hook callbacks increment a counter
  -> 600 post-entry callbacks reached
  -> temporarily clear only TVMD.DISP
  -> hold display blank for 120 display frames
  -> restore exact TVMD
  -> proof complete
```

The two-second display blank is intentionally unmistakable and does not depend
on L, R, or any other controller bit. It also avoids VRAM, CRAM, VDP1, Work RAM
capture, SD writes, and direct SMPC polling. The proof refuses to steal an
already occupied SAROO/SRK game breakpoint.

Interpretation is strict:

- **Blank appears and restores:** recurring `cdp_hook` execution after title entry
  has been physically demonstrated.
- **No blank appears:** do not blame controller decoding; the recurring callback
  itself has not been demonstrated and the runtime-menu architecture must move
  to a different recurring execution mechanism.

## Planned validation order

1. One-shot post-launch UBR execution — already physically demonstrated.
2. Armed, input-independent recurring execution proof after title entry (R6).
3. Only if R6 succeeds, characterize fresh controller samples after the callback.
4. Rebuild the modal lifecycle on the proven recurring callback.
5. Minimal text shell with `SRK` / `Resume` only.
6. Physical text-menu enter/resume validation.
7. `Capture Both`.
8. Individual WRAM-H / WRAM-L captures.
9. Mark / metadata.
10. Bounded recording controls.

Each stage must remain title-neutral in public SRK code and should be promoted
only after the preceding hardware-dependent claim has actually been observed on
real hardware.
