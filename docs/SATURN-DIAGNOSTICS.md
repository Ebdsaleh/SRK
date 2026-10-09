# SRK Saturn Diagnostics

SRK's standalone Saturn diagnostics program is the controlled hardware-validation environment for the runtime features that will later be reused by resident/injected tooling.

The standalone program is intentionally developed before further commercial-title injection work. A standalone Saturn application owns its own input, interrupt, video, timing, and memory environment, so failures can be attributed to SRK instead of being mixed with an unknown title engine.

## Development ladder

SRK now separates three environments:

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

The menu shell, Controller / Input Test, Flight Recorder, and Video Pattern Test are implemented. Video Pattern Test is physically accepted on real Saturn hardware. VDP1 / 3D Test is now the active hardware tranche; the remaining entries stay explicit placeholders until their hardware backends are implemented and reviewed.

## Host boundary

The diagnostic core does not know how a controller packet, screen, timer, VBR observation, video pattern, or future storage operation is obtained. `srk_diag_host.h` defines the boundary.

A standalone Saturn host may use direct Saturn hardware services. A later resident host can provide the same normalized services through a different safe mechanism. This keeps menu, recorder, input-state, and pattern-selection logic reusable instead of baking SAROO/BIOS or one title's assumptions into the core.

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

The first 3D workload is a rotating cube driven by SH-2-side transforms and rendered through VDP1. It should exercise:

```text
X/Y/Z rotation
perspective projection
near/far scaling
face ordering
VDP1 command generation
frame pacing
changing face hues
```

The diagnostic should expose useful raw counters beside the visual result rather than treating the cube as a visual-only demo.

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

### R5 — accepted physical baseline

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

The deployable R5 image was generated as a single-track MODE1/2352 BIN/CUE pair, freshly verified against the intermediate ISO, deployed through SRK's guarded SAROO workflow, and followed by a whole-card inventory verification that matched the pre-deployment baseline except for the explicitly allowed new R5 directory and its BIN/CUE files.

R5 remains a known-good physical-hardware rollback/reference baseline for subsequent standalone Saturn diagnostic work.

### R6 — Video Pattern Test physically accepted

R6 completed the first hardware video-diagnostic tranche and was physically accepted on a real Sega Saturn on 2026-10-09.

The R6 image was built from the source-gated Video Pattern implementation, compiled with the reviewed SH-ELF toolchain, packaged as a verified single-track MODE1/2352 BIN/CUE pair, deployed beside R5 as `TEST/SRK-Diagnostics-R6`, and followed by a whole-card guard verification that returned `MATCH` with only the new R6 directory and its BIN/CUE files allowed.

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

R6 is the current known-good physical-hardware baseline for standalone video diagnostics.

## Current validation boundary

SRK now has a physically proven standalone Saturn host supplying real controller sampling, VBlank-paced timing, VBR observation, stable VDP2 bitmap text presentation, a physically accepted Video Pattern Test, and a bootable verified BIN/CUE deployment path.

This proves the current standalone master-mode foundation; it does **not** establish cooperative-resident or foreign-resident safety. The active milestone is now the VDP1 / 3D diagnostic, beginning with a minimal attributable VDP1 primitive path before the rotating cube workload.
