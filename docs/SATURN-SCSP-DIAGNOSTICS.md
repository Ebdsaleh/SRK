# SRK Saturn Audio / SCSP Diagnostics

This document records the reviewed hardware contract for the first standalone
`Audio / SCSP Test` milestone.

SRK keeps the same architecture used for Video Pattern and VDP1 diagnostics:
logical diagnostic state stays title-neutral, while the standalone Saturn host
owns direct hardware addresses and register encodings. A future resident host
must be free to implement the same logical requests through a different safe
mechanism.

## Evidence policy

Hardware behavior for this tranche is based on the supplied Sega Saturn
technical documentation, with the local Saturn development/sample environment
used as corroborating implementation evidence.

Primary hardware references include:

- Sega Saturn SCSP User's Manual (`ST-77` family);
- Sega Saturn SMPC User's Manual;
- Sega Technical Bulletin #51 concerning MC68EC000 sound-CPU operation;
- the supplied Sega SGL/SBL material.

The locally supplied Rockin'-B SoundPlayer example, including `RB_playPCM.c`, is
useful corroboration for Saturn PCM workflows, but Stage 1 does not import its
library-dependent player into SRK. SRK's first proof remains deliberately small,
freestanding, and attributable.

## Stage 1 goal

Prove the shortest controlled audio path:

```text
real Saturn controller
        |
        v
SRK title-neutral audio state
        |
        v
standalone Saturn audio host
        |
        +-- Sound RAM waveform
        +-- SCSP slot 0
        +-- pitch
        +-- direct send level
        +-- direct pan
        |
        v
physical Saturn audio output
```

Stage 1 is not a music player, filesystem player, CDDA test, streaming test, or
DSP-effects test. Those add independent variables and belong in later stages.

## Core / host ownership

The reusable diagnostic core owns only:

```text
LOW / MID / HIGH logical tone identity
LEFT / CENTER / RIGHT logical pan identity
volume level 0..7
PLAYING / STOPPED
MUTED / AUDIBLE
controller policy
labels and diagnostic lifecycle
```

The core must not contain Saturn Sound RAM, SCSP, or SMPC addresses.

The standalone hardware backend owns:

```text
SMPC SNDON / SNDOFF command issue
safe command timing
Sound RAM address/layout
MC68EC000 dummy program
SCSP common-control setup
SCSP slot-0 register layout
16-bit PCM waveform installation
OCT/FNS pitch encoding
DISDL/DIPAN encoding
KYONB/KYONEX sequencing
raw register/status readback
```

## Controls

Stage 1 uses edge-triggered controls so every state transition is attributable:

```text
A              Play / Stop
C              Mute / Unmute
LEFT           Hard left
UP             Center
RIGHT          Hard right
X              LOW tone
Y              MID tone
Z              HIGH tone
L              Volume down one step
R              Volume up one step
START          Stop owned slot and return to diagnostics menu
```

If L and R arrive on the same sample, the volume change cancels.

Tone selection has deterministic same-sample priority `Z > Y > X`. Pan selection
has deterministic same-sample priority `UP > LEFT > RIGHT`.

Reset state is:

```text
tone     MID
pan      CENTER
volume   4
state    STOPPED
output   AUDIBLE (not muted)
```

No audio is keyed on merely by entering the screen. The user explicitly starts
the proof with A.

## Conservative output level

SCSP direct-send level (`DISDL`) provides a hardware-defined 0..7 ladder. Stage
1 exposes that exact logical range and starts at level 4 rather than maximum.

The generated square-wave samples also use only one quarter of signed 16-bit
full scale (`+0x2000` / `-0x2000`). Together with the mid-level default direct
send, this gives the first physical test deliberate headroom.

Volume 0 is a hardware send level of zero. Level 7 is the maximum Stage-1 direct
send for this bounded waveform; it does not mean that every future Saturn audio
path is globally at maximum level.

## Deterministic waveform

Stage 1 creates its own small waveform instead of loading a WAV/PCM file:

```text
16-bit signed PCM
normal loop
100-sample nominal period
samples 0..49   = +0x2000
samples 50..99  = -0x2000
loop-end sample = +0x2000
```

The loop-end sample deliberately matches the loop-start sample, following the
SCSP normal-loop boundary requirement.

The UI calls the three pitches only `LOW`, `MID`, and `HIGH`. It does not claim
an exact audible frequency because Stage 1 is proving deterministic relative
pitch manipulation, not calibrating a frequency standard.

The current pitch words use FNS=0 and adjacent OCT settings:

```text
LOW   OCT=-1   0x7800
MID   OCT= 0   0x0000
HIGH  OCT=+1   0x0800
```

Thus each selection is an octave relation around the same stored waveform.

## Pan contract

The standalone backend uses the SCSP direct-pan table:

```text
LEFT    DIPAN 0x1F
CENTER  DIPAN 0x00
RIGHT   DIPAN 0x0F
```

The names are intentionally player/listener-facing. Physical validation must
confirm that LEFT is heard only from the left output, CENTER from both, and RIGHT
only from the right output.

## Sound Direct path

Stage 1 sets the slot's Sound Direct mode so envelope, total-level, and LFO
processing do not obscure the primitive proof. The test controls output level
through the final direct-send field instead.

This is intentionally not the final architecture for game audio. It is the
smallest SCSP slot-to-DAC proof with the fewest independently variable blocks.

## Main-CPU access width

The Sega SCSP documentation prohibits main-side byte access to Sound RAM / SCSP
space. The standalone backend therefore represents these regions as 16-bit
volatile words and performs word accesses for its Sound RAM and SCSP setup.

The reusable core never sees those addresses.

## Sound CPU lifecycle

SMPC `SNDOFF` is used only for the bounded setup window required to establish a
known Sound-RAM/SCSP state.

Sega Technical Bulletin #51 warns against leaving the MC68EC000 sound CPU
stopped for extended periods even when the application does not otherwise need
it. Stage 1 therefore installs a tiny dummy program before `SNDON` and leaves the
sound CPU running afterward.

The dummy environment is deliberately defensive:

```text
256 exception vectors -> 0x00000400
reset stack pointer   -> 0x0007FFF0
reset program counter -> 0x00000400
0x00000400            -> BRA.S to itself
```

The waveform lives separately at Sound RAM byte address `0x00002000`.

Returning from the Audio screen keys off SRK's slot and removes its direct send;
it does **not** leave the sound CPU stopped.

## SMPC timing

`SNDON` and `SNDOFF` are SMPC commands. The SMPC documentation defines a command
issue exclusion window immediately after V-BLANK-IN. Since the diagnostic shell
synchronizes frames around V-BLANK, the one-time Audio initialization waits out
that unsafe interval before issuing the setup command pair.

Command issue follows the reviewed SF/COMREG handshake rather than assuming a
fixed CPU delay.

## Slot ownership

Stage 1 owns only SCSP slot 0 for the test tone. During first initialization it
requests key-off for the SCSP slots before establishing its known slot-0 state.
The Stage-1 test is a master-mode standalone program and therefore owns the sound
hardware; the same policy must **not** be copied blindly into a future resident
host that coexists with a running title.

That master-mode vs resident-mode distinction is the reason SCSP register access
stays in the host layer.

## On-screen telemetry

The Audio screen exposes both logical state and raw host observations:

```text
Host submit
PLAYING / STOPPED
MUTED / AUDIBLE
LOW / MID / HIGH
LEFT / CENTER / RIGHT
volume 0..7
SCSP initialization state
SCSP common-control word
slot-0 control word
slot-0 pitch word
slot-0 mixer word
```

Raw words remain visible so physical photographs/video can be compared with the
requested logical state instead of relying only on what is heard.

## Physical acceptance plan

The first Audio image must preserve every previous diagnostics baseline and must
also carry the corrected VDP1 Stage-3 shoulder-roll mapping.

Required physical checks:

```text
R10 boots normally
Controller / Input Test remains operational
Video Pattern Test remains operational
VDP1 / 3D Test remains operational
VDP1 L rolls left / counter-clockwise
VDP1 R rolls right / clockwise
Audio / SCSP Test opens without hang
initial Audio state is STOPPED / MID / CENTER / volume 4 / AUDIBLE
A starts and stops the tone
LEFT is left-only
UP is centered / both channels
RIGHT is right-only
X/Y/Z are clearly low/mid/high relative pitches
L lowers volume one step at a time
R raises volume one step at a time
volume 0 is silent
C mutes and unmutes without changing tone/pan/volume state
raw SCSP telemetry changes consistently with requests
START immediately silences SRK's slot and returns to the menu
no tone leaks into another diagnostic screen
no video flashing or unrelated subsystem regression occurs
```

Only after those checks should Audio / SCSP Stage 1 be physically accepted.

## Later stages

After Stage 1 physical acceptance, useful attributable extensions are:

1. independent simultaneous left/right source proof;
2. deterministic pitch sweep and volume ramp;
3. richer in-memory PCM/sample playback;
4. streaming / filesystem-backed playback where separately justified;
5. SCSP DSP/effect work only after the simpler slot/mixer path is established.

Each stage should remain independently observable and reversible rather than
jumping directly to a complex music-player workload.
