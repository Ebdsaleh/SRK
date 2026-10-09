# Saturn SCSP Diagnostic — Stage 3 Deterministic Pitch / Volume Sweep

Stage 3 extends the physically accepted Stage 1 single-slot and Stage 2 stereo-pair diagnostics with an automated, repeatable pitch/level sequence.

## Goal

Prove on real Saturn hardware that SRK can repeatedly change an active SCSP voice's reviewed pitch selection and direct-send level over time without introducing a new waveform, a new SCSP pitch encoding, or a new hardware ownership model.

This stage deliberately reuses only hardware values already accepted in earlier stages:

- LOW: OCT=-1, FNS=0 (`0x7800`)
- MID: OCT=0, FNS=0 (`0x0000`)
- HIGH: OCT=+1, FNS=0 (`0x0800`)
- direct-send volume levels `0..7`
- CENTER pan
- the same deterministic signed 16-bit square-wave sample

No calibrated-Hz claim is made. Stage 3 is a deterministic relative-pitch and level-transition proof.

## Control

`DOWN+B` toggles the automated sweep.

The chord has priority over ordinary `B` stereo-mode toggling on the same controller sample.

When the sweep starts, SRK establishes a known state:

- single-slot mode;
- CENTER pan;
- playing;
- unmuted;
- LOW tone;
- volume 0;
- sweep frame 0.

While the sweep is active, ordinary Audio-screen controls are ignored so the sequence cannot be perturbed accidentally. `DOWN+B` exits the sweep. `START` still stops owned audio and leaves the screen; a later re-entry does not silently resume the automation.

## Sequence

The sweep contains 48 logical steps. Each step lasts 15 displayed frames.

The six 8-step phases are:

1. LOW, volume `0 -> 7`
2. MID, volume `0 -> 7`
3. HIGH, volume `0 -> 7`
4. HIGH, volume `7 -> 0`
5. MID, volume `7 -> 0`
6. LOW, volume `7 -> 0`

After step 47 the sequence wraps to step 0 and repeats until explicitly stopped.

At nominal display rates this is approximately:

- 12 seconds per complete cycle at 60 Hz;
- 14.4 seconds per complete cycle at 50 Hz.

Those durations are descriptive only; the diagnostic contract is frame-count based.

## Architecture

Stage 3 remains title-neutral in the reusable diagnostics core.

The core owns:

- sweep active/inactive state;
- frame and logical-step progression;
- selection of LOW/MID/HIGH logical tone IDs;
- logical volume `0..7`;
- CENTER pan policy;
- controller priority.

The standalone backend is unchanged. It continues to translate the existing logical tone IDs and volume levels into the already reviewed SCSP pitch and DISDL encodings.

This is intentional: Stage 3 proves temporal control of the accepted path without introducing another hardware variable.

## R13 physical acceptance

Stage 3 is physically accepted on real Sega Saturn hardware in R13.

The physical pass confirmed the requested Stage 3 behavior, including the deterministic pitch/volume sequence, repeat behavior, explicit `DOWN+B` stop path, and START teardown/non-resume behavior. The user reported the test worked as specified.

R13 was built and deployed through the preserve-first one-command workflow before physical testing:

- build result: SUCCESS;
- MODE1/2352 sectors: 64;
- BIN SHA-256: `d49ee0b19579ab385cdc7bd5a8df5e52aeaf6370b8e13b89057270d231bf0ad6`;
- CUE SHA-256: `5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950`;
- whole-card verification: MATCH;
- final deployment result: VERIFIED AND SAFE TO EJECT.

Stage 1 and Stage 2 remain preserved physical baselines; Stage 3 does not supersede or rewrite their accepted behavior.
