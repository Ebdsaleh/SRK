# Saturn Audio — Silent MC68EC000 MIDI Command Engine

## Status entering this tranche

R18 is a physically accepted real-Saturn baseline.

The accepted hardware proof established:

```text
SH-2
  -> Saturn Sound RAM
  -> resident SRK MC68EC000 image
  -> MC68EC000 execution
  -> mailbox acknowledgement
  -> SH-2 observes sequence/index/error
```

Physical PASS was:

```text
ACKNOWLEDGED
READ_SEQUENCE = 1
READ_INDEX    = 1
LAST_ERROR    = 0
```

The final standalone Audio/SCSP diagnostic also passed on real hardware by
direct operator observation.

R18 remains unchanged.  This tranche does not replace the accepted R18
consumer image and does not enable MIDI-driven SCSP voice writes.

## Purpose

The next driver layer must understand more than the single fixed proof record
before SRK is allowed to make MIDI-driven sound.

This tranche therefore defines a deterministic **silent command/state engine**
for one bounded SRKM queue batch.

It consumes:

```text
NOTE_OFF
NOTE_ON
POLY_AFTERTOUCH
CONTROL_CHANGE
PROGRAM_CHANGE
CHANNEL_PRESSURE
PITCH_BEND
```

and produces deterministic channel state plus a complete queue acknowledgement.

No SCSP slot, mixer, DSP or voice register is written by this layer.

## Sound-RAM state reservation

The existing bounded MIDI queue ends at:

```text
0x00001200
```

The established standalone Audio/SCSP ownership begins at:

```text
0x00002000
```

The new silent state is constrained entirely inside that gap:

```text
0x1200-0x13FF  channel summaries
0x1400-0x1BFF  128 controller bytes x 16 channels
0x1C00-0x1CFF  128-note logical-key bitmap x 16 channels
0x1D00-0x1DFF  reserved telemetry
0x1E00-0x1FFF  deliberately left unused
```

The validator rejects any future change that crosses the `0x2000` audio
boundary.

## Per-channel summary

Each of the 16 MIDI channels owns exactly 16 Sound-RAM words:

```text
word  0  program
word  1  bank MSB
word  2  bank LSB
word  3  volume
word  4  pan
word  5  expression
word  6  sustain
word  7  channel pressure
word  8  14-bit pitch bend
word  9  last note
word 10  last velocity
word 11  last poly-aftertouch note
word 12  last poly-aftertouch pressure
word 13  active logical-note count
word 14  consumed event count
word 15  last SRKM opcode
```

`0xFFFF` is the sentinel for a channel that has no previous note.

The complete 128-controller state is also retained independently instead of
only preserving the small subset needed by the current diagnostic.

## Deterministic reset state

The SRK driver model starts each channel at:

```text
bank MSB       0
bank LSB       0
program        0
volume         100
pan            64
expression     127
sustain        off
channel press  0
pitch bend     8192 (centre)
notes          all released
```

These are explicit SRK driver defaults.  They are not inferred from uninitialised
Sound RAM.

## Note semantics

The engine tracks logical note velocity for all 128 notes on every channel.

```text
NOTE_ON velocity > 0 -> logical note becomes active
NOTE_ON velocity = 0 -> logical note becomes released
NOTE_OFF             -> logical note becomes released
```

The active-note bitmap represents logical key state only.  Sustain is tracked
separately; later voice-allocation policy will decide when a released key's
voice may actually be reclaimed while sustain is active.

This separation is deliberate so the command parser is not coupled to a future
SCSP voice policy.

## Controller semantics in this tranche

Every Control Change stores its exact 7-bit value in the 128-entry per-channel
controller table.

The channel summary additionally mirrors the controllers already required by
the existing deterministic diagnostic:

```text
CC  0  bank MSB
CC 32  bank LSB
CC  7  volume
CC 10  pan
CC 11  expression
CC 64  sustain
```

Other controller numbers are preserved in the full controller table and remain
available to later policy layers.

## Queue acknowledgement

One invocation consumes one already-published bounded SRKM batch.

The engine refuses:

```text
zero-record batches
more than 32 records
out-of-order timestamps
invalid channels
non-7-bit MIDI data
invalid SRKM opcodes
zero/out-of-range mailbox write sequence
```

Only after every record succeeds does the result expose:

```text
read_index    = complete record count
read_sequence = supplied write sequence
last_error    = 0
```

This is the multi-record extension of the physical R18 acknowledgement concept.

## Canonical deterministic workload

The existing SRK-owned diagnostic MIDI already supplies a useful first workload:

```text
27 SRKM records
2 active musical channels
bank select
program changes
volume
pan
expression
sustain
pitch bend
Note On
Note Off
velocity-zero Note On normalization
```

After all 27 records are silently consumed, both diagnostic channels have no
logical notes left active.

The regression suite checks the exact final program/controller state for both
channels.

## External CC0 assets

External CC0 WAV/MIDI assets are intentionally not required by this tranche.

They become valuable after the deterministic engine and later voice allocator
are proven:

```text
single-instrument MIDI -> first bounded audible MIDI voice test
CC0 WAV                 -> sample/import playback-path testing
Double Impact MIDI set  -> later multi-channel/polyphony workload
```

Keeping those assets outside the current source gate means this command engine
remains reproducible from the repository alone.

## Next gate

This tranche is still a model/contract gate.  The next implementation step is:

```text
encode the reviewed state transitions into a new resident MC68EC000 image
-> compile/image stability gate
-> full standalone build gate
-> guarded silent physical candidate
```

That candidate should still make no MIDI-driven SCSP sound.

Only after the real MC68EC000 consumes the multi-record batch and returns the
expected final state should SRK proceed to deterministic voice allocation and
the first MIDI-driven SCSP note.

R18 remains the accepted silent physical recovery/validation baseline.

> Safer is secure, secure is faster.
