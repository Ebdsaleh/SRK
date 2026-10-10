# Saturn Audio — MIDI Playback Foundation

SRK treats MIDI-file playback as a standard-console audio capability. External
physical MIDI input/output hardware is explicitly out of scope for this project.

The architecture is intentionally split before any Saturn-specific playback code
is added:

```text
Standard MIDI File
        |
        v
formats/midi.py
(strict structural decode)
        |
        v
core/midi_sequence.py
(tempo + channel-state schedule)
        |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
Saturn diagnostic     Mjolnir inspect    Flight recorder
playback backend      / correlation      audio observatory
```

## Current normalized timing contract

For SMF format 0/1 files using PPQN timing, SRK:

- starts with the standard 500000 microseconds-per-quarter default tempo;
- applies `set_tempo` events at their absolute tick;
- preserves exact fractional time internally between tempo boundaries;
- emits deterministic whole-microsecond timestamps;
- uses merged event order `(tick, track index, event index)`;
- lets the final tempo event at one tick own the following segment.

SMF format 2 is not silently merged because its tracks are independent
sequences. SMPTE timing remains preserved by the parser but is rejected by this
PPQN scheduler until a dedicated SMPTE clock policy is implemented.

## Current normalized channel state

The scheduler tracks explicit state independently for all 16 MIDI channels:

- bank select MSB (CC 0);
- bank select LSB (CC 32);
- program change;
- volume (CC 7);
- pan (CC 10);
- expression (CC 11);
- sustain pedal (CC 64);
- 14-bit pitch bend.

Bank/program/mix values begin as unknown rather than inventing a General MIDI
profile that the source file did not declare. Pitch bend begins at the defined
14-bit centre value and sustain begins released.

Every scheduled channel event carries the state after that event has been
applied. A note event therefore carries the complete known controller/program
state active when the note occurs.

## Saturn boundary

This layer does **not** yet map MIDI channels or programs to SCSP slots, Sound
RAM, Sega tone banks, or 68EC000 commands. That mapping belongs in the Saturn
diagnostic backend and must be proven separately on hardware.

The first hardware MIDI-file proof should use an SRK-owned deterministic
sequence and SRK-owned sample/tone data. It must not depend on external MIDI
interfaces or optional hardware.

## Flight-recorder reuse

The same normalized schedule is intended to support later events such as:

```text
SEQUENCE_START
MIDI_BANK
MIDI_PROGRAM
MIDI_NOTE_ON
MIDI_NOTE_OFF
MIDI_CONTROL_CHANGE
MIDI_PITCH_BEND
SEQUENCE_STOP
```

Those events can then be correlated with text, scene state, sample-bank loads,
SCSP slot activity, streamed PCM, and CD-DA activity without coupling the
observer to one game's sound driver.
