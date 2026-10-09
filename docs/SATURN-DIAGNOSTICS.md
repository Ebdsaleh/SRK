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

The menu shell, Controller / Input Test, Flight Recorder, Video Pattern Test, VDP1 static primitive path, rotating-cube path, and interactive cube-dynamics path are implemented. Video Pattern Test and VDP1 Stage 1 are physically accepted on real Saturn hardware; R8 physically proves the Stage 2 rotating-cube visual/animation path; and R9 physically proves the Stage 3 interaction model with one attributable shoulder-roll polarity defect. The next Stage 3 correction maps L/R to player-facing counter-clockwise/clockwise roll without changing the mathematical transform convention. The remaining entries stay explicit placeholders until their hardware backends are implemented and reviewed.

## Host boundary

The diagnostic core does not know how a controller packet, screen, timer, VBR observation, video pattern, VDP1 command list, or future storage operation is obtained. `srk_diag_host.h` defines the boundary.

A standalone Saturn host may use direct Saturn hardware services. A later resident host can provide the same normalized services through a different safe mechanism. This keeps menu, recorder, input-state, pattern-selection, logical-geometry, 3D-transform, and interactive-dynamics code reusable instead of baking SAROO/BIOS or one title's assumptions into the core.

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

For VDP1 Stage 3, the existing frame-by-frame raw/normalized/pressed/released/held controller samples already provide the input stream needed to replay deterministic cube dynamics from a known reset state. A future recorder-format extension may add direct cube-state snapshots, but that is deliberately deferred until the control model itself is physically accepted.

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

### Stage 2 — rotating cube — physical visual/animation proof

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

R8 physically proves the central Stage 2 visual/animation goal. The supplied hardware video shows a clearly three-dimensional cube continuously changing orientation with different colored face combinations visible over time while the VDP2 diagnostic shell remains present and stable. The cube remains bounded near screen center and the raw VDP1 status/animation telemetry remains visible.

The R8 recording does not independently demonstrate the START teardown/no-leak sequence, so those lifecycle checks remain mandatory regressions for subsequent physical builds rather than being inferred from the video.

### Stage 3 — interactive deterministic cube dynamics — active

Stage 3 turns the rotating cube from a canned animation into a deterministic controller-to-render hardware manipulation test.

The core owns fixed-point angular velocity, speed, freeze state, palette state, and input-driven acceleration. Controller input changes **velocity**, not absolute orientation, so the existing diagonal motion can be influenced gradually rather than snapped to a fixed axis.

The player-facing control contract is:

```text
UP / DOWN     pitch acceleration (X velocity)
LEFT / RIGHT  yaw acceleration (Y velocity)
L / R         counter-clockwise / clockwise roll acceleration (Z velocity)
A / B         increase / decrease global speed scalar
C             toggle frozen / running motion
X             exact PASTEL palette
Y             exact NEON palette
Z             restore exact ORIGINAL R8 palette
START         hide VDP1 and return to diagnostics menu
```

Positive mathematical Z rotation is counter-clockwise under the existing transform. The transform remains mathematically conventional; the controller mapping carries the player-facing policy: **L adds positive Z acceleration for counter-clockwise/left roll, while R adds negative Z acceleration for clockwise/right roll.** This deliberately separates coordinate-system convention from control intent.

Opposing controls cancel acceleration on that axis. Releasing a directional/shoulder control preserves angular momentum; there is no automatic damping in the first Stage 3 implementation. Velocity and speed are explicitly clamped.

The motion representation is Q8 fixed point:

```text
angle accumulators: Q8 phase
angular velocities: signed Q8 phase/frame
speed scalar: Q8, where 256 = 1.0x
initial VX/VY/VZ: +256
initial speed: 256
velocity clamp: +/-1536
speed clamp: 0..1024
```

With no Stage 3 input, reset therefore reproduces the accepted R8 motion exactly: +1 phase/frame on X, Y, and Z at 1.0x speed.

C freeze preserves current orientation, velocity, and speed exactly. While frozen the frame/status surface and palette selection stay live; motion integration stops. Unfreezing resumes from the preserved state.

The palette controls select three fixed six-face RGB8 tables rather than performing subjective runtime saturation math. This keeps photographic/capture expectations deterministic. The Saturn host still owns RGB8-to-RGB1555 conversion.

Stage 3 telemetry exposes:

```text
RUN / FROZEN
palette mode
speed Q8
VX / VY / VZ
X / Y / Z phase
visible face count
animation frame
EDSR / LOPR / COPR / MODR
```

The VDP2 bitmap must still never be globally cleared every frame; only dynamic fields are overwritten in place, preserving the R5+ anti-flashing architecture.

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

R7 is therefore the known-good physical VDP1 primitive baseline and the rollback point for later animation work.

### R8 — VDP1 Stage 2 rotating-cube visual proof

R8 completed the first fixed-point animated 3D workload on physical Sega Saturn hardware on 2026-10-09.

The initial R8 generated project exposed one historical-toolchain compatibility issue: SH-ELF GCC lowered legal small aggregate copies into external `_memcpy` calls while the image deliberately links with `-nostdlib`. SRK retained the freestanding contract by changing cube transform/projection helpers to caller-owned outputs and adding a minimal SH-2 `_memcpy` compiler-ABI helper to the standalone startup runtime. Regression coverage locks both behaviours.

The fixed R8 project then passed all compile, assemble, link, ISO, and MODE1/2352 packaging gates. It was deployed in parallel as `TEST/SRK-Diagnostics-R8`, followed by a whole-card verification returning `MATCH` with only the new R8 directory and its BIN/CUE files allowed.

Physical video evidence establishes:

```text
R8 boots and reaches VDP1 / 3D Test
a clearly three-dimensional cube renders through VDP1
cube orientation changes continuously across the recording
multiple differently colored faces become visible over time
perspective remains bounded near the intended screen-center area
VDP2 diagnostic text remains visible around the VDP1 scene
raw VDP1 status and animation telemetry remain visible
no obvious recurrence of the R4 whole-screen flashing defect
```

The supplied R8 clip does not independently show START teardown or post-return leakage checks. Those lifecycle behaviours remain required regression checks in the next physical validation cycle.

R8 is therefore the known-good physical visual/animation reference for Stage 3 interactive-dynamics work.

### R9 — VDP1 Stage 3 interactive dynamics physical proof with one polarity defect

R9 was source-gated, compiled with the reviewed SH-ELF toolchain, linked freestanding, packaged as a verified 64-sector MODE1/2352 BIN/CUE image, deployed beside R5-R8, and followed by a whole-card verification returning `MATCH`.

Physical Saturn testing established that the interactive Stage 3 workload is operational: the cube remains a stable VDP1 3D object while real controller input changes its motion state, the Stage 3 telemetry remains visible, and the exact face-palette modes can be exercised on hardware. Direct physical observation identified one attributable control-policy defect: **L produced clockwise roll and R produced counter-clockwise roll**, opposite the intended player-facing contract.

The defect was not a VDP1 rendering or matrix-correctness failure. The existing Z transform follows the conventional positive-angle sign, where positive Z appears counter-clockwise. R9 had mapped L to decreasing Z velocity and R to increasing Z velocity. The correction therefore preserves the transform and swaps only the input-to-Z acceleration policy:

```text
L -> +Z acceleration -> counter-clockwise / left roll
R -> -Z acceleration -> clockwise / right roll
```

R9 is retained unchanged as physical provenance for the Stage 3 interaction proof and the discovered polarity defect. A new parallel candidate is required to physically close Stage 3 after the corrected shoulder mapping is source-gated and built.

## Current validation boundary

SRK now has a physically proven standalone Saturn host supplying real controller sampling, VBlank-paced timing, VBR observation, stable VDP2 bitmap text presentation, physically accepted Video Pattern diagnostics, a physically accepted VDP1 primitive path, a physical fixed-point animated-cube visual proof, and an operational interactive fixed-point cube workload on physical Saturn hardware.

This proves the current standalone master-mode foundation; it does **not** establish cooperative-resident or foreign-resident safety. Stage 3 remains open only for physical confirmation of the corrected player-facing L/R roll polarity; the geometry transform, acceleration/inertia model, speed control, freeze state, exact palette modes, VDP1 host boundary, and live telemetry remain otherwise unchanged.
