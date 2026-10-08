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

Those facts did **not** by themselves prove continuous or recurring SRK execution
while normal gameplay proceeds. That required the later resident proof.

## Controller-sample caveat

The original runtime-hook integration samples the BIOS controller memory at
`0x06020232` before invoking SAROO's original BIOS routine. The exact freshness
and recurrence semantics of that memory location during arbitrary commercial
gameplay have not yet been physically established.

During later testing, holding L+R in the SAROO menu could also be interpreted by
the menu as repeated actions. That menu uses its own edge/state logic and is not
identical to the in-game 16-bit sample path, so the behavior does not by itself
explain the in-game failure. It does, however, reinforce the requirement that
SRK test controller observation only from a proven resident execution path.

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
is treated primarily as an observability/callback problem rather than a renderer
problem.

## Armed post-entry execution proof (R6)

R6 removed controller input from the question. It was armed in the SAROO menu,
gated on the already proven dynamic IP.BIN 1st-read UBR event, then counted later
`cdp_hook` invocations. Reaching 600 callbacks would blank `TVMD.DISP` for 120
frames before exact restore.

The physical experiment was **inconclusive by design**, not a positive or
negative recurring-callback result. The temporary blank could occur during a
normal publisher/developer splash transition and therefore could not be
unambiguously distinguished by the operator. Skipping splash screens made the
ambiguity worse. A transient visual event is no longer considered sufficient
proof for this milestone.

R6 remains useful as evidence that the diagnostic path can be built and deployed
safely, but it does not establish recurring runtime execution.

## Persistent resident-runtime proof (R7) — physically rejected

R7 switched to the BIOS interrupt trampoline present in upstream SAROO's
`RUN_CHEAT`/`CHEAT_patch` code. The proof was armed explicitly before game
launch, wrote a persistent `ARMED` slot, verified the exact BIOS instruction
shape at `0x0600090C`, installed the hook after `patch_game()`, and wrote a
persistent `INSTALLED` slot.

Two independent armed hardware runs with Darius Gaiden reproduced the same
failure: the title froze while loading. Unarmed A/B runs booted and played
normally. Both 96-byte proof artifacts contained valid `ARMED` and `INSTALLED`
slots and no `PROVEN` slot. The installed timestamps occurred roughly 8.52 s and
8.13 s after arming. R7 is therefore **physically rejected as a stable runtime
callback path**.

The post-build SH-2 disassembly identified a concrete context-corruption bug.
The BIOS SCU interrupt handler has already saved `r1-r5` before the patched site,
but `r0` remains the interrupt-vector index and the original handler does not
save `r6` and `r7` until `0x0600091C` and `0x06000920`. R7 called an ordinary C
function before those saves. The compiled fast path of
`srk_runtime_resident_proof_tick()` uses `r6` for the callback counter on every
invocation, so the first callback can overwrite the interrupted title's live
`r6` before the BIOS preserves it.

This also narrows the interpretation of the upstream SAROO precedent. Its
`RUN_CHEAT` wrapper has the same C ABI exposure around an optional callback, but
upstream `patch_game()` resets `CHEAT_ADDRES` to zero. The mere presence of that
optional call site is therefore not sufficient evidence that an arbitrary C
callback is context-safe at this point in the BIOS handler.

## Context-safe persistent resident proof (R8) — physically proven

R8 retained the useful R7 persistence format and exact BIOS-shape verification,
but replaced the compiler-generated vector entry with a dedicated SH-2 assembly
trampoline.

Before executing any SRK C code, the assembly wrapper preserves the BIOS-live
state that the original handler has not yet protected:

```text
r0
r6
r7
PR
GBR
MACH
MACL
```

It then replays the exact displaced BIOS instructions from
`0x0600090C-0x06000918`, saves the BIOS-selected SR, raises the interrupt mask to
15 while the SRK callback executes, restores the saved special/general state,
restores the BIOS-selected SR, and resumes at `0x0600091A`.

The generated SH-2 disassembly was inspected before deployment and matched that
save/replay/call/restore sequence exactly. The guarded candidate was:

```text
ssfirm.bin
size:    484246 bytes
SHA-256: d2e07f46aa81f1bc6ebc3d0785f7b353f2a4456611e6b54754c1983e052e12f4
```

On original Saturn hardware, the persistent proof reached all three stages:

```text
ARMED
INSTALLED
PROVEN — callback count 600
```

The hardware timestamps were:

```text
arm       18415897
installed 27656614   (+9.240717 s from arm)
proven    31064538   (+12.648641 s from arm)
                       +3.407924 s from installation
```

The exact 96-byte proven artifact was preserved off-card with SHA-256:

```text
b10d0c5d5da1983659b14b4d7fb155e55a546f3cbc184d04a7b592a58b0c3d9c
```

This is persistent physical evidence that the cartridge-resident SRK callback
was entered 600 times after installation through the running title-launch
lifetime. It replaces the earlier transient visual inference with a durable
artifact. The proof does not by itself claim indefinite residency after the
600th callback because R8 deliberately restores the BIOS vector immediately
once `PROVEN` is written.

The decoded BIOS path at `0x0600090C` is the HBLANK-IN handler for SCU vector
`0x42`. That matters for input work: resident callback frequency is display-line
interrupt frequency when enabled, not controller-sample frequency. Future input
logic must therefore rate-limit observations rather than counting every
trampoline entry as a fresh pad sample.

## R9 — rate-limited resident runtime-input proof

R9 asks the next narrow question without adding a renderer or direct SMPC I/O:
can the physically proven resident trampoline remain installed until the player
intentionally holds L+R, and can SRK persist that activation?

The R9 lifecycle is:

```text
SRK Arm Runtime Input
  -> create/truncate /SAROO/SRK_RUNTIME_INPUT_PROOF.BIN to exactly 96 bytes
  -> write ARMED slot
  -> launch title
  -> verify and install the context-safe HBLANK-IN trampoline after patch_game()
  -> write INSTALLED slot
  -> remain resident with no waiting-path SD I/O
  -> observe BIOS controller-1 memory at 0x06020232
  -> rate-limit observations to one every 20000 SS_TIMER ticks (20 ms)
  -> require L+R for 50 rate-limited samples (~1 second)
  -> write one 32-byte ACTIVATED slot
  -> restore the original BIOS HBLANK-IN vector
```

The existing title-neutral `srk_runtime_input` detector remains responsible for
the release-gated L+R state machine. Rate limiting is deliberately outside that
helper so its semantics remain reusable while R9 prevents HBLANK frequency from
artificially satisfying the 50-sample threshold in milliseconds.

The R9 proof slot records the observed 16-bit button value, total resident
callback count, rate-limited input sample count, `SS_TIMER`, elapsed ticks from
arm, sample period, and hold threshold. It performs no VDP writes, Work RAM
capture, UBR operation, or direct SMPC command.

R9 is a diagnostic bridge, not the final runtime menu. Hardware acceptance
requires intentionally waiting after title launch before holding L+R so a valid
`ACTIVATED` artifact demonstrates both continued residency and controller
observation after the launch window.

## Planned validation order

1. One-shot post-launch UBR execution — physically demonstrated.
2. R6 transient recurring-callback proof — physically inconclusive; do not use as evidence.
3. R7 persistent BIOS-trampoline proof — physically rejected; reproducible armed freeze traced to pre-save register clobber.
4. R8 context-safe assembly trampoline — **physically proven to 600 callbacks** with persistent evidence.
5. R9 rate-limited controller proof from the proven resident HBLANK-IN path.
6. Add a persistent snapshot trigger and then a VDP/VRAM capture package for offline frame reconstruction.
7. Rebuild the modal lifecycle on the proven resident callback.
8. Minimal text shell with `SRK` / `Resume` only.
9. Physical text-menu enter/resume validation.
10. `Capture Both` and individual WRAM capture actions.
11. Mark / metadata and bounded recording controls.

Each stage must remain title-neutral in public SRK code and should be promoted
only after the preceding hardware-dependent claim has actually been observed on
real hardware.
