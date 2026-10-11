# Saturn MIDI / MC68EC000 R23 first-note source gate

## Purpose

R22A is the immutable real-Saturn stream/scheduler baseline. It physically proved
continuous resident MC68EC000 execution, timestamp gating, same-queue refill,
two acknowledgement sequences, persistent MIDI command state and complete
1408-word state equality.

R23 begins the next risk boundary: **MIDI-driven SCSP audio**.

This source gate deliberately does not jump directly to general polyphony. The
first audio tranche closes one narrow capability completely:

```text
SRKM NOTE_ON
-> deterministic voice allocation
-> resident MC68EC000 SCSP slot programming
-> audible sustained PCM tone
-> scheduled NOTE_OFF
-> deterministic release
```

R22A remains unchanged.

## Hardware truth source

R23 reuses the register pattern already exercised by SRK's standalone Saturn
Audio / SCSP diagnostic rather than introducing a second set of SCSP semantics.

The MC68EC000-visible map used by the new resident image is:

```text
Sound RAM                  : 0x000000-0x07FFFF
SCSP slot register base    : 0x100000
slot size                  : 0x20 bytes
slot count                 : 32
SCSP common register base  : 0x100400
```

The first voice owns only slot 0.

The direct-PCM slot fields match the existing diagnostic vocabulary:

```text
control : word 0
SA low  : word 1
LSA     : word 2
LEA     : word 3
EG1     : word 4
EG2     : word 5
TL      : word 6
FM      : word 7
pitch   : word 8
LFO     : word 9
DSP     : word 10
mixer   : word 11
```

Keying uses the already-reviewed `KYONB` / `KYONEX` sequence.

## R23 Sound-RAM ownership

The accepted R22A MIDI control/state ranges below `0x2000` are unchanged.
R23 begins audio ownership at the pre-existing Audio/SCSP boundary:

```text
0x2000-0x20FF : deterministic direct-PCM waveform area
0x2100-0x21FF : R23 voice-allocation state / telemetry
0x2200-0x22FF : 128-entry MIDI-note -> SCSP-pitch table
0x2300-0x3FFF : untouched by R23 audio data
0x4000-...    : resident MC68EC000 program
```

The test waveform is the same reviewed square-wave convention used by the
standalone diagnostic:

```text
50 samples  : +0x2000
50 samples  :  0xE000
loop end    : 100
endpoint    : +0x2000
```

## Voice allocator policy

The R23 allocator is intentionally bounded:

```text
owned voices : 1
owned slot   : 0
policy       : monophonic
voice steal  : disabled
retrigger    : same channel + same note only
```

A different note arriving while slot 0 is active is recorded as a voice-busy
condition. It is not allowed to steal the active voice in this first tranche.

This keeps the first hardware-audio proof independent from later decisions about
polyphonic priority, age, percussion policy and stealing.

## First-note proof contract

The source/model proof is exactly two SRKM records:

```text
0 us:
  NOTE_ON
  channel 3
  note 60
  velocity 100

1,000,000 us:
  NOTE_OFF
  channel 3
  note 60
```

For note 60, the reviewed pitch mapping is `0x0000`. The proof mixer is center
pan at the deterministic velocity-100 level (`0xC000`).

The future physical wrapper must keep the producer-published clock below the
second event's due time long enough for the note to be audibly sustained before
publishing `1,000,000 us` and allowing NOTE_OFF to execute.

## Voice-state telemetry

R23 maintains a small Sound-RAM ledger independently of the SCSP registers:

```text
magic / version
owned-slot count
active flag
slot
MIDI channel
MIDI note
velocity
generation
SCSP pitch
SCSP mixer
SCSP control
key-on count
key-off count
last allocator error
```

The later physical proof must compare both this ledger and the relevant actual
SCSP slot registers. Audible sound alone is not sufficient acceptance evidence.

## Legacy compiler gate

The first R23 user validation is intentionally off-card.

It compiles:

```text
resident R23 image representation
existing R22A-compatible SH-2 refill/timebase producer
voice-state declaration
```

using the production legacy SH-ELF compiler policy.

The compiler gate:

```text
does not link a Saturn executable
does not install the resident image
does not execute MC68EC000 code
does not perform Sound-RAM writes
does not execute SCSP MMIO
does not write the SAROO card
```

The generated resident *image* contains SCSP-access instructions by design;
that is different from the compiler gate executing those instructions.

## Physical-candidate requirements after compiler acceptance

A later R23 physical candidate must be derived through fresh, independently
reviewed artifacts and must not mutate R22A.

Its run should prove, in order:

```text
1. explicit fresh user action arms the proof
2. accepted sound-CPU stop/install/start path succeeds
3. resident R23 service reaches ready state
4. two-record batch is published with producer clock = 0
5. NOTE_ON executes and slot-0 voice ledger becomes active
6. actual slot-0 control/source/pitch/mixer registers match the reviewed state
7. clock remains below 1,000,000 us during a bounded audible hold
8. an audible tone is physically observed during that hold
9. producer publishes 1,000,000 us
10. NOTE_OFF executes
11. slot-0 voice ledger becomes inactive
12. actual slot-0 mixer/key state is released/silent
13. logical MIDI state and mailbox acknowledgement are correct
```

Only after a guarded real-Saturn candidate produces both correct telemetry and
audible MIDI-driven sound can R23 become a physical acceptance baseline.

## Explicit exclusions

R23 first-note does **not** yet claim:

```text
polyphony
voice stealing
sustain-pedal-held physical voices
live CC7/CC10/CC11 mixer updates
live pitch-bend retuning
program/bank -> instrument selection
percussion mapping
full Standard MIDI File playback through SCSP
hardware-derived production timing source
```

Those capabilities should build on the physically accepted first-note path
rather than being mixed into the first SCSP-write risk.

## Safety boundary

R17-R21 and R22A remain immutable. R22 remains preserved as the historical
wrapper-false-negative evidence. Existing candidate directories and accepted
SAROO images must not be overwritten or redeployed.

R23 source/model/compiler work is off-card until a later independent build,
pre-media review and whole-card guarded deployment explicitly authorize a fresh
`SRK-Diagnostics-R23` destination.
