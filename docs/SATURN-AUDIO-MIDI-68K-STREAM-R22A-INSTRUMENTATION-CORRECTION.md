# Saturn MIDI 68K stream proof — R22 physical wrapper failure / R22A correction

R22 was deployed through the reviewed independent pre-media and whole-card guard
pipeline and then exercised on real Saturn hardware.

Two physical runs were captured:

- one after other diagnostics had been exercised;
- one after a reboot followed directly by `MIDI 68K Stream Proof`.

The targeted reboot run reproduced the same terminal failure, excluding prior
suite activity as the cause.

## What the hardware actually proved

Before the terminal error, the physical telemetry reached:

```text
Read sequence : 2
Read index    : 8
Batch count   : 2
Total records : 40
Wait @ 0us    : 1
15ms = 15     : 1
Batch1 ACK    : 1
Refill wait   : 1
Batch2 ACK    : 1
State verify  : 1
CC74          : 31
Program       : 12
```

`State verify = 1` is the complete R22 state verifier.  It compares the entire
reviewed state surface:

```text
256 channel-summary words
1024 controller words
128 active-note words
```

Therefore the real MC68EC000 resident service successfully proved the intended
32+8 queue refill, timestamp milestones, sequence-1 / sequence-2 completion, and
persistent MIDI state across the refill.

## False terminal failure

The terminal screen reported:

```text
Last error  : 57364
             = 0xE014
Final pitch : 64
```

`0xE014` is the redundant selected-state capture comparison performed *after*
the complete state verifier has already passed.

The physical value `64` identified the defect: channel 3 pan defaults to 64.
The selected-state capture computed channel-summary addresses by adding the
summary constants directly as bytes, even though those constants are word
indexes.

For channel 3, the summary base is `0x1260`:

```text
program word index       0  -> byte address 0x1260
pitch-bend word index    8  -> byte address 0x1270
active-count word index 13  -> byte address 0x127A
```

R22 instead generated:

```text
pitch  : 0x1268 -> channel pan -> 64
active : 0x126D -> address>>1 aliases 0x126C -> sustain
```

The resident engine and the complete state verifier were not using these
incorrect selected-state addresses.

## R22A policy

R22 is preserved unchanged as physical evidence.  It is not overwritten or
silently reclassified as a clean terminal PASS.

R22A is a fresh candidate derived from the accepted inert stream/scheduler
baseline.  It changes only the generated selected-state capture addresses:

```text
PROGRAM_ADDRESS      0x00001260
PITCH_ADDRESS        0x00001270
ACTIVE_COUNT_ADDRESS 0x0000127A
```

R22A does **not** change:

- the compiler-accepted resident MC68EC000 stream image;
- the SH-2 producer;
- the 40-record proof program;
- the 32+8 split;
- the 0 / 15000 / 32000 / 40000 us milestones;
- the full 1408-word verifier;
- any SCSP behavior (still silent).

R22A must pass its own fresh standalone build, independent pre-media review,
whole-card PREPARE/APPLY guard, and first-terminal-result physical run before it
is accepted as an immutable physical baseline.
