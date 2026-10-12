# Saturn Audio / MIDI 68K R25 — RR Physical Calibration Source Gate

R25 reached this gate only after the four-slot HELD/RELEASING resident service and the inert 32-value RR compiler matrix passed on Eridu.

This tranche is **source/model only**. It does not install or execute the MC68EC000 service, access SCSP/FRT hardware, build an ISO, touch SAROO media, or select a production RR.

## Accepted production anchor

The accepted compiler matrix at `ce0afbb927f4a61ff5849d70ea2cb5ff62df2676` produced this RR16 image under the production 120-ms ownership policy:

```text
RR                16
EG1               0x001F
EG2               0x3C10
image SHA-256     002e9d102b88e4f21a64dbeb768eb3c66726493a735487be1ae8194a706ed0a2
object SHA-256    0f54df500b72d942f52f5d778dab7f8a89992a72419a096132354e90ea0a11fd
production tail   120000 us
```

The calibration renderer verifies the accepted RR16 image before and after every calibration render. The production resident generator is not modified by this tranche.

## Why calibration needs a separate ownership window

The production service retires a RELEASING slot after 120000 us. Reusing that deadline while trying to measure an unknown SCSP release rate would force every naturally slower tail to end at 120 ms and bias the measurement.

The calibration-only renderer therefore uses:

```text
observation / ownership window   2000000 us
```

The override exists only during one synchronous image/header/source render and is restored in `finally`. The exact accepted production RR16 hash must still match afterward.

This 2-second window is an observation bound, **not** a claim that the selected RR lasts two seconds.

## Deterministic physical probe model

Every later physical calibration build must require an explicit RR value. The first planned probe is RR16, but RR16 is not selected for production.

The source-gated stimulus is:

```text
channel             0
note                69 (A4)
velocity            100
Note On             250000 us
Note Off            1250000 us
held duration       1000000 us
observation window  2000000 us after Note Off
observation end     3250000 us
records             2
stream batches      1
```

The production-selection flag remains `False`.

## Hardware measurement boundary

The Sega SCSP slot-status monitor exposes the selected slot's current waveform address (`CA`). It does not expose an envelope level or envelope-phase field suitable for detecting the instant that a release reaches silence.

Therefore the later physical calibration must combine deterministic machine timing with operator/audio observation. It must not claim automatic SCSP silence detection.

## Safety boundary

This tranche performs no:

- MC68EC000 execution;
- SCSP MMIO;
- SH-2 FRT MMIO;
- Sound RAM hardware writes;
- standalone ISO build;
- installation into a Saturn project;
- SAROO planning or writes;
- RR production selection.

The next authorized tranche, after this source gate passes on Eridu, is a **fresh off-card R25 calibration candidate/full-build gate** derived from the accepted R24 physical Saturn/FRT project. It must preserve R24 and use a fresh output directory. No card deployment is authorized by this document.
