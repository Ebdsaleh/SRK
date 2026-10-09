# SRK Saturn Diagnostics

SRK's standalone Saturn diagnostics program is the controlled hardware-validation environment for the runtime features that will later be reused by resident/injected tooling.

The standalone program is intentionally developed before further commercial-title injection work.  A standalone Saturn application owns its own input, interrupt, video, timing, and memory environment, so failures can be attributed to SRK instead of being mixed with an unknown title engine.

## Development ladder

SRK now separates three environments:

1. **Master mode** — a bootable SRK Saturn program owns the machine and proves each subsystem independently.
2. **Cooperative resident mode** — an SRK-controlled homebrew workload acts like a game while the diagnostic/runtime core proves context save/restore and coexistence.
3. **Foreign resident mode** — the proven runtime is adapted to an unrelated running title.

Standalone success does not by itself establish foreign-runtime safety.  Machine-owning operations such as changing VBR, configuring VDP state, direct SMPC access, claiming Work RAM, or performing synchronous storage work remain host responsibilities.

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

The first implemented core screens are the menu shell, Controller / Input Test, and Flight Recorder.  Other entries remain explicit placeholders until their hardware backends are implemented and reviewed.

## Host boundary

The diagnostic core does not know how a controller packet, screen, timer, VBR observation, or future storage operation is obtained.  `srk_diag_host.h` defines the boundary.

A standalone Saturn host may use direct Saturn hardware services.  A later resident host can provide the same normalized services through a different safe mechanism.  This keeps menu, recorder, and input-state logic reusable instead of baking SAROO/BIOS or one title's assumptions into the core.

The core must therefore not depend on the R9 BIOS snapshot address, SAROO `SS_TIMER`, or SAROO file-writing calls.

## Controller / Input Test

The input test keeps both views of every sample:

```text
raw hardware word
        +
host-normalized SRK button mask
```

The raw value is deliberately visible on screen.  If the host's interpretation is ever wrong, the hardware evidence is still available.

The normalized state tracks all digital buttons simultaneously and distinguishes:

```text
PRESSED
HELD
RELEASED
hold duration
multi-button combinations
```

L+R receives an explicit combination display and duration because a future resident runtime-menu gesture needs physical evidence that both shoulder buttons can be observed continuously for a controlled interval.

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

`value0` and `value1` are diagnostic-specific telemetry fields.  The initial application shell uses them for the L+R combination hold duration and controller state-change count.

The recorder can be armed/reset and later frozen.  When full it overwrites the oldest record, preserving the most recent 30 seconds instead of merely collecting the first 30 seconds.

Persistent export is deliberately deferred until a standalone Saturn storage backend has itself been validated.  Capture and recording state must remain separable from storage.

## Planned video tests

The video test should grow in small, independently validated steps:

```text
solid black / white / red / green / blue
hue sweep
brightness ramp
RGB bars
checkerboards
fine grid / line patterns
overscan and safe-area pattern
VDP2 background tests
VDP1 primitive tests
priority / transparency / composition tests
```

Every pattern should identify itself on screen so photographs and capture-card recordings remain self-describing.

## Planned VDP1 / 3D test

The first 3D workload is a rotating cube driven by SH-2-side transforms and rendered through VDP1.  It should exercise:

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

R8/R9 showed why interrupt assumptions must be measurable.  The timing/interrupt screen should eventually expose quantities such as VBLANK/HBLANK counts, frame duration, current VBR, and reviewed SCU/SMPC status observations.

## Planned memory / dump tools

Initial dump targets remain:

```text
WRAM-H
WRAM-L
Both Work RAM regions
```

Future diagnostic targets may include VDP1 VRAM, VDP2 VRAM, CRAM, sound RAM, and a system-state package, but only when their capture semantics are explicit.

Capture and export remain separate operations internally.  No diagnostic core function should assume that a SAROO SD-card filesystem is automatically available to a standalone CD application.

## Current validation boundary

At the current source milestone, the diagnostic contracts and hardware-neutral C core exist, including input edges/holds/combinations, menu state, the 30-second ring recorder, and a host-driven application shell.

This does **not** yet mean a Saturn BIN/CUE has been built or physically booted.  The next hardware milestone is a standalone Saturn host that supplies real timing, direct controller sampling, and a minimal text renderer to this core, followed by construction of a bootable image and physical validation.
