# Saturn MIDI / 68K R24 Real-SMF Source Gate

R23 is the immutable first-audio physical baseline.  It proved real MIDI event -> resident MC68EC000 -> SCSP key-on -> audible output -> scheduled key-off on a physical Saturn.

R24 raises the acceptance target from one diagnostic oscillator event to complete playback of a real Standard MIDI File.

## First real-song target

The selected source is the existing CC0 repository asset:

```text
assets/midi/cc0/melody-town-theme/Melody Town Theme.mid
```

The source asset remains immutable.  SRK reads it through the existing platform-neutral SMF parser, tempo scheduler and SRKM v1 compiler.

Locked source SHA-256:

```text
9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041
```

Reviewed source/program contract:

```text
SMF format                 : 1
Tracks                     : 3
PPQN                       : 96
Tempo                      : 845070 us/quarter (~71 BPM)
SRKM records               : 310
Duration                   : 108151354 us
Note On                    : 140
Note Off                   : 140
Control Change             : 23
Program Change             : 3
Pitch Bend                 : 4
Note range                 : 71..86
Peak simultaneous notes    : 2
Two-note overlap points    : 4
Queue batches              : 10
Batch sizes                : 32,32,32,32,32,32,32,32,32,22
```

The four two-note overlap entry times are:

```text
30404914 us
41813359 us
84480591 us
95889036 us
```

## R24 pitch correction

R23 deliberately mapped MIDI note 60 to SCSP pitch zero on the existing 100-sample direct-PCM diagnostic loop.  The real hardware recording measured the resulting oscillator around 440 Hz, so R23 proved routing/keying rather than calibrated musical pitch.

R24 treats the nominal zero-pitch waveform fundamental as:

```text
44100 samples/s / 100 samples = 441 Hz
```

For each MIDI note, R24 computes the equal-tempered target frequency from A4 = 440 Hz, then selects the nearest SCSP OCT/FNS playback multiplier.  The complete MIDI 0..127 table must remain below one cent of quantisation error.

This explicitly replaces the R23 diagnostic `note 60 -> pitch 0` relationship for future musical playback.  R23 itself remains unchanged.

## R24 voice policy

The reference song requires at most two simultaneous notes.  The first complete-song allocator therefore owns exactly:

```text
SCSP slot 0
SCSP slot 1
```

Policy:

```text
allocation      : lowest free owned slot
same-key repeat : retrigger existing owner
voice stealing  : disabled
third voice     : deterministic busy/error path
```

The complete reference program must finish with:

```text
key-on count  : 140
key-off count : 140
peak active   : 2
busy count    : 0
active voices : 0
```

This is deliberately enough polyphony for the selected real song without prematurely introducing a general stealing policy.

## R24 complete-song producer

The 310 records are split into ten existing 32-record Sound-RAM queue refills.

The new SH-2 producer:

1. receives monotonic microseconds from an external clock backend;
2. publishes that value through the accepted stream-service seqlock;
3. publishes batch 1;
4. waits for resident acknowledgement of sequence 1;
5. publishes batch 2;
6. repeats through sequence 10;
7. completes only after sequence 10 is acknowledged.

The producer contains no synthetic milestone timer and no physical-clock register access.  Time source and MIDI/refill semantics are intentionally separated.

## R24 hardware-clock boundary

R22/R23 synthetic producer clocks are not acceptable for real-song playback.

R24 adds a platform-neutral monotonic clock model and records the Saturn SH-2 FRT register geometry:

```text
TIER  : 0xFFFFFE10
FTCSR : 0xFFFFFE11
FRC-H : 0xFFFFFE12
FRC-L : 0xFFFFFE13
TCR   : 0xFFFFFE16
TOCR  : 0xFFFFFE17
```

The host model extends the 16-bit FRT across wraps and converts ticks using an explicit rational calibration supplied by the physical backend.  It intentionally does **not** hard-code one Saturn CPU frequency because the final backend must account for the active hardware/video clock mode.

A previously proven SAROO 1 MHz timer also exists, but R24 does not bake SAROO-specific timing into the player.  A physical proof backend may be compared against it during clock validation.

## Current source/model files

```text
src/rikai_kotoba/hardware/saturn/midi_68k_r24_song.py
src/rikai_kotoba/hardware/saturn/midi_68k_r24_pitch.py
src/rikai_kotoba/hardware/saturn/midi_68k_r24_voice_allocator.py
src/rikai_kotoba/hardware/saturn/midi_68k_r24_clock.py
src/rikai_kotoba/hardware/saturn/midi_68k_r24_player.py
```

Tests:

```text
tests/test_saturn_midi_68k_r24_song.py
tests/test_saturn_midi_68k_r24_pitch.py
tests/test_saturn_midi_68k_r24_voice_allocator.py
tests/test_saturn_midi_68k_r24_clock.py
tests/test_saturn_midi_68k_r24_player.py
```

## Current safety boundary

This source gate performs no Saturn hardware I/O and makes no SAROO writes.

There is no deployable R24 image in this tranche.

R23 remains immutable.

## Next gate after host validation

After the real-SMF source/model tests pass on the user's machine, R24 should add a **new** resident MC68EC000 image and compile gate that matches the two-slot allocator and calibrated pitch table, then an inert full integration of the complete 310-event producer.

Only after compiler and inert integration acceptance should R24 gain a fresh callable physical candidate, independent pre-media review, and whole-card guarded deployment.

Physical R24 acceptance is not a single tone.  It requires recognisable, complete playback of the selected real `.mid` file with correct event order, refill continuity, musical pitch, both required simultaneous voices, and a clean final key-off state.
