# SRK Saturn Diagnostics

SRK's standalone Saturn diagnostics program is the controlled hardware-validation environment for runtime features that will later be reused by resident/injected tooling.

The standalone program is intentionally developed before further commercial-title injection work. A standalone Saturn application owns its own input, interrupt, video, timing, and memory environment, so failures can be attributed to SRK instead of being mixed with an unknown title engine.

## Development ladder

SRK separates three environments:

1. **Master mode** — a bootable SRK Saturn program owns the machine and proves each subsystem independently.
2. **Cooperative resident mode** — an SRK-controlled homebrew workload acts like a game while the diagnostic/runtime core proves context save/restore and coexistence.
3. **Foreign resident mode** — the proven runtime is adapted to an unrelated running title.

Standalone success does not by itself establish foreign-runtime safety. Machine-owning operations such as changing VBR, configuring VDP state, direct SMPC access, claiming Work RAM, or performing synchronous storage work remain host responsibilities.

## Diagnostic menu

The stable title-neutral menu contract is:

```text
SRK SATURN DIAGNOSTICS

> Controller / Input Test
  Video Pattern Test
  VDP1 / 3D Test
  Audio / SCSP Test
  Timing / Interrupt Test
  Memory / Dump Tools
  Flight Recorder
  System Information
```

The menu shell, Controller / Input Test, Flight Recorder, Video Pattern Test, and the first VDP1 primitive path are implemented. Video Pattern Test and VDP1 Stage 1 are physically accepted on real Saturn hardware. VDP1 Stage 2 — the rotating-cube workload — is now the active hardware tranche. The remaining entries stay explicit placeholders until their hardware backends are implemented and reviewed.

## Host boundary

The diagnostic core does not know how a controller packet, screen, timer, VBR observation, video pattern, VDP1 command list, or future storage operation is obtained. `srk_diag_host.h` defines the boundary.

A standalone Saturn host may use direct Saturn hardware services. A later resident host can provide the same normalized services through a different safe mechanism. This keeps menu, recorder, input-state, pattern-selection, logical-geometry, and 3D-transform code reusable instead of baking SAROO/BIOS or one title's assumptions into the core.

The core must therefore not depend on the R9 BIOS snapshot address, SAROO `SS_TIMER`, SAROO file-writing calls, or direct Saturn video register addresses.

## Controller / Input Test

The input test keeps both views of every sample:

```text
raw hardware word
        +
host-normalized SRK button mask
```

The raw value is deliberately visible on screen. If the host's interpretation is ever wrong, the hardware evidence is still available.

The normalized state tracks all digital buttons simultaneously and distinguishes:

```text
PRESSED
HELD
RELEASED
hold duration
multi-button combinations
```

L+R receives an explicit combination display and duration because a future resident runtime-menu gesture needs physical evidence that both shoulder buttons can be observed continuously for a controlled interval.

START is testable like every other digital button. In Controller / Input Test only, `L+R+START` is the explicit return gesture so START itself can be observed as PRESSED/HELD/RELEASED.

The standalone host, not the core, is responsible for mapping the real Saturn controller protocol to SRK's normalized button mask.

## Flight recorder

The application flight recorder is a reusable rolling telemetry subsystem rather than a one-off test.

Current contract:

```text
30-second rolling window
maximum assumed frame sampling rate: 60 Hz
capacity: 1800 records
record size: 32 bytes
RAM footprint: 57,600 bytes
```

Each record contains:

```text
timestamp_us
frame
raw_pad
normalized_pad
pressed
released
held
diagnostic_id
vbr
value0
value1
```

`value0` and `value1` are diagnostic-specific telemetry fields. The initial application shell uses them for the L+R combination hold duration and controller state-change count.

The recorder can be armed/reset and later frozen. When full it overwrites the oldest record, preserving the most recent 30 seconds instead of merely collecting the first 30 seconds.

Persistent export is deliberately deferred until a standalone Saturn storage backend has itself been validated. Capture and recording state must remain separable from storage.

## Video Pattern Test architecture

Video Pattern Test deliberately separates **pattern selection** from **pixel generation**.

The title-neutral diagnostic core owns:

```text
current pattern identity
LEFT/RIGHT navigation
pattern labels
screen lifecycle
```

The active host owns:

```text
actual framebuffer / VDP configuration
palette / CRAM programming
pixel generation
hardware-specific presentation
```

For standalone master mode, the Saturn host may render directly through the already-proven VDP2 bitmap surface. A later cooperative or foreign-resident host can implement the same logical pattern request through a different safe presentation path without introducing Saturn register addresses into the diagnostic core.

The first pattern set is intentionally simple and attributable:

```text
solid black
solid white
solid red
solid green
solid blue
RGB / color bars
grayscale / brightness ramp
checkerboard
fine grid
overscan / safe-area pattern
```

Each pattern identifies itself on screen so photographs and capture recordings remain self-describing.

## VDP1 / 3D Test — active milestone

The VDP1 milestone is deliberately split into attributable stages.

### Stage 1 — static primitive proof — physically accepted

The title-neutral diagnostic core owns one logical RGB quadrilateral and submits that geometry through the host boundary. It does **not** know VDP1 VRAM addresses, command-table layout, framebuffer registers, VDP2 sprite-composition registers, or RGB1555 encoding.

The standalone Saturn host owns:

```text
VDP1 command-table construction
system-clipping initialization
non-textured polygon command generation
RGB1555 conversion
VDP1 framebuffer / drawing control
VDP2 sprite RGB/composition setup
primitive teardown on diagnostic exit
```

Stage 1 also exposes these raw VDP1 registers on screen:

```text
EDSR
LOPR
COPR
MODR
```

R7 physically proved this path on a real Saturn. The static colored quadrilateral rendered in the intended lower-center area while the VDP2 diagnostic text stayed visible. The hardware screen reported `Host submit: OK`, one submission, and live raw VDP1 status values. Previous Controller/Input and Video Pattern functions were also rechecked successfully.

### Stage 2 — rotating cube — active

Stage 2 reuses the physically proven Stage 1 VDP1 path but moves 3D state and math into the title-neutral core. The core owns:

```text
object-space cube vertices
six logical faces and per-face colors
animation angles / frame counter
fixed-point X/Y/Z rotation
perspective projection
visible-face selection
far-to-near face ordering
projected logical quads
```

The standalone Saturn host continues to own VDP1 command-table construction, RGB1555 conversion, hardware drawing control, VDP2 composition, raw status reads, and teardown.

The first animated cube should remain deliberately simple and attributable: deterministic fixed-point transforms, a fixed camera distance and focal length, painter-style face ordering, distinct face colors, and no textures or lighting. The diagnostic keeps raw VDP1 status visible beside animation telemetry so a hardware failure is not reduced to a visual-only observation.

## Planned audio test

The audio section is intended to prove SCSP-facing behavior independently with simple, attributable cases such as left/right tones, stereo, frequency sweeps, volume ramps, and later PCM playback.

## Planned timing / interrupt test

Earlier runtime experiments showed why interrupt assumptions must be measurable. The timing/interrupt screen should eventually expose quantities such as VBLANK/HBLANK counts, frame duration, current VBR, and reviewed SCU/SMPC status observations.

## Planned memory / dump tools

Initial dump targets remain:

```text
WRAM-H
WRAM-L
Both Work RAM regions
```

Future diagnostic targets may include VDP1 VRAM, VDP2 VRAM, CRAM, sound RAM, and a system-state package, but only when their capture semantics are explicit.

Capture and export remain separate operations internally. No diagnostic core function should assume that a SAROO SD-card filesystem is automatically available to a standalone CD application.

## Physical hardware validation

### R4 — first physical Saturn boot

R4 established the first end-to-end physical proof of SRK Saturn Diagnostics:

```text
SRK source
  -> SH-2 compile/link
  -> Saturn boot image
  -> MODE1/2352 BIN/CUE
  -> SAROO
  -> physical Sega Saturn
```

The menu booted and navigated on hardware, and Controller / Input Test received real controller state. R4 also exposed two attributable defects: the visible bitmap was being cleared and repainted every display frame, causing severe flashing, and START was consumed as an exit action before it could be meaningfully tested.

### R5 — accepted controller/menu baseline

R5 corrected both defects and was physically accepted on 2026-10-09.

Validated behavior on the real Saturn includes:

```text
stable menu rendering without continuous full-screen flashing
real controller input visible as raw and normalized state
START visibly reports PRESSED / HELD / RELEASED
START alone remains inside Controller / Input Test
L+R+START returns from Controller / Input Test
menu navigation remains operational
other diagnostic entries remain reachable
```

R5 remains a known-good physical-hardware rollback/reference baseline.

### R6 — Video Pattern Test physically accepted

R6 completed the first hardware video-diagnostic tranche and was physically accepted on a real Sega Saturn on 2026-10-09.

Physical validation established:

```text
R6 boots through SAROO
stable diagnostics menu with no recurrence of R4 full-screen flashing
Video Pattern Test opens and remains stable
LEFT/RIGHT advances through the diagnostic pattern set
solid black / white / red / green / blue patterns render correctly
RGB / color bars render correctly
grayscale / brightness ramp renders correctly
checkerboard renders correctly
fine-grid and safe-area geometry render correctly
START returns cleanly to the diagnostics menu
normal diagnostics rendering is restored after returning from the video screen
```

The accompanying camera recording shows exposure/white-balance shifts while bright and saturated patterns are displayed. Direct human-eye observation of the physical display reported the colors themselves as correct; the camera behavior is therefore recorded as a capture artifact, not as a Saturn rendering defect.

R6 remains the known-good physical-hardware baseline for standalone video diagnostics.

### R7 — VDP1 Stage 1 physically accepted

R7 completed the first VDP1 hardware tranche and was physically accepted on a real Sega Saturn on 2026-10-09.

The R7 image was source-gated, built with the reviewed SH-ELF toolchain, packaged as a verified MODE1/2352 BIN/CUE pair, deployed beside R5 and R6 as `TEST/SRK-Diagnostics-R7`, and followed by a whole-card guard verification that returned `MATCH` with only the new R7 directory and its BIN/CUE files allowed.

Physical validation established:

```text
R7 boots through SAROO
previous Controller/Input and Video Pattern functions remain operational
VDP1 / 3D Test opens without crash or hang
VDP2 diagnostic text remains stable and visible
host reports successful VDP1 submission
one colored VDP1 quadrilateral appears in the lower-center region
raw EDSR / LOPR / COPR / MODR values are visible
no recurrence of uncontrolled full-screen flashing
```

Photographic evidence records the live Stage 1 screen with:

```text
Host submit: OK
Submissions: 1
EDSR: 0x0003
LOPR: 0x000C
COPR: 0x000C
MODR: 0x1140
```

R7 is therefore the current known-good physical VDP1 primitive baseline and the rollback point for Stage 2 animation work.

## Current validation boundary

SRK now has a physically proven standalone Saturn host supplying real controller sampling, VBlank-paced timing, VBR observation, stable VDP2 bitmap text presentation, physically accepted Video Pattern diagnostics, and a physically accepted VDP1 primitive path with raw hardware status.

This proves the current standalone master-mode foundation; it does **not** establish cooperative-resident or foreign-resident safety. The active milestone is now VDP1 / 3D Stage 2: animate a title-neutral fixed-point rotating cube through the already-proven host-rendered VDP1 path.
