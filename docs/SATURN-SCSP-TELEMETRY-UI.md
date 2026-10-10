# Saturn SCSP Diagnostics — Stages 1-5 Telemetry Presentation Closure

This tranche closes the presentation/observability gap left after the Stage 5 hardware proof.

It does **not** introduce a new SCSP mode, Sound-RAM source, hardware constant, controller contract, or audio ownership rule. The physically accepted Stages 1-5 behavior remains the functional baseline.

## Purpose

The Audio / SCSP screen originally retained its Stage 1 presentation even after the diagnostic backend had advanced through:

- Stage 1 single-slot deterministic tone;
- Stage 2 same-source stereo pair;
- Stage 3 deterministic pitch/level sweep;
- Stage 4 alternate shaped PCM source;
- Stage 5 heterogeneous two-slot/two-source pair.

Stage 5 already exposed raw per-slot source and loop telemetry through the title-neutral host status, but the screen did not display those fields. This closure makes the state already available in the core/backend visible on hardware before SRK advances to a larger packaged/file-backed PCM milestone.

## No hardware behavior change

This tranche changes only diagnostic presentation plus its regression contract.

It does not change:

- SMPC SNDON/SNDOFF values or timing;
- Sound CPU lifecycle;
- Sound-RAM PCM regions;
- slot source retargeting rules;
- LOW/MID/HIGH pitch encodings;
- DIPAN listener-left/center/listener-right mapping;
- DISDL volume encoding;
- KYONB/KYONEX handling;
- Stage 2, 3, 4, or 5 activation controls.

## Logical presentation

The Audio screen now identifies the current logical mode explicitly:

```text
SINGLE
STEREO
SWEEP
SHAPED
MIXED
```

It separately displays the logical source label already supplied by the Audio core:

```text
TONE
SHAPED PCM
TONE+PCM
```

Tone, pan, volume, playing/stopped, muted/audible, and host-submit status remain visible.

## Raw SCSP observations

The screen now renders the already exposed raw observations for both owned diagnostic slots:

```text
Common SCSP control
SCSP READY state

S0 source      S1 source
S0 LEA         S1 LEA
S0 pitch       S1 pitch
S0 mixer       S1 mixer
S0 control     S1 control
```

For the physically accepted Stage 5 mixed pair, the key source observations are expected to be:

```text
S0 source = 0x2000
S0 LEA    = 0x0064
S1 source = 0x2400
S1 LEA    = 0x0100
```

Both Stage 5 slots use MID pitch intentionally, so both pitch observations should show the accepted MID encoding while the pair is active.

## Current control legend

The screen now documents the current Stages 1-5 controller surface rather than the old Stage 1-only legend:

```text
A Play/Stop   C Mute/Unmute
LEFT/UP/RIGHT Select L/Both/R
X/Y/Z Tone Low/Mid/High
L/R Volume   DOWN+A Stereo
DOWN+B Sweep  DOWN+C Shaped
DOWN+Z Mixed pair
START Stop + return to diagnostics menu
```

## R16 presentation acceptance target

A fresh R16 candidate should be used as a bounded physical presentation/telemetry proof before introducing a larger Stage 6 audio input path.

Physical acceptance should confirm:

1. the Audio screen renders stably with no R4-style flashing;
2. no labels overlap or visibly truncate important telemetry;
3. SINGLE/STEREO/SWEEP/SHAPED/MIXED mode labels follow the selected control path;
4. TONE/SHAPED PCM/TONE+PCM source labels follow the selected source mode;
5. Stage 5 MIXED mode displays the expected slot-0/slot-1 source and LEA observations;
6. LEFT/RIGHT/UP isolation visibly changes the corresponding mixer observations as expected while physical audio remains correct;
7. Stage 1-5 audio behavior is otherwise unchanged;
8. START still silences owned audio and returns cleanly;
9. Input, Video, and VDP1 diagnostics remain stable.

Only presentation/observability is under test in R16. A failure here must not be interpreted as a reason to alter physically accepted SCSP constants unless separate hardware evidence supports that conclusion.

After this closure is physically accepted, the next major audio milestone can move beyond synthetic/in-memory generation toward a guarded packaged/file-backed PCM payload path.
