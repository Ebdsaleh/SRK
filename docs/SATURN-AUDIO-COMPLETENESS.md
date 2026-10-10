# Saturn Audio Completeness Roadmap

SRK's Saturn audio work now has two deliberate outputs:

1. a standalone, title-neutral hardware diagnostic that exercises the major audio paths available on a normal Sega Saturn; and
2. a reusable audio-observation vocabulary for the flight recorder and later localization/replacement tooling.

The diagnostic and observatory must share the same concepts instead of growing as unrelated one-off tools.

## Scope boundary

The standard-console completion target includes:

- SCSP PCM playback;
- 8-bit and 16-bit sample paths;
- loop modes and loop-boundary behavior;
- envelope, pitch and LFO behavior;
- modulation/FM behavior;
- multi-slot/polyphony behavior;
- 68EC000-driven sound-control behavior;
- MIDI/sequence **file playback semantics** such as note on/off, bank/program selection, controller volume/pan and pitch bend;
- streamed PCM buffering;
- DSP/effect routing;
- CD-DA playback and SCSP-side mixing/routing;
- bounded Sound RAM integrity/stress diagnostics;
- telemetry suitable for later flight-recorder event decoding.

External physical MIDI input/output is explicitly outside this project's completion requirement. A stock-console diagnostic must not depend on MIDI interface hardware the project cannot physically validate. Likewise, optional MPEG/Video-CD hardware remains an optional peripheral-specific extension rather than a blocker for normal-console completion.

## MIDI policy

"MIDI support" in the core diagnostic means deterministic playback of Standard MIDI File data through an SRK-controlled Saturn sound path.

The first implementation layer is a title-neutral Standard MIDI File parser owned by SRK. It must decode timing and the channel events needed by the diagnostic without relying on external MIDI devices:

- note on;
- note off, including note-on velocity zero;
- program change;
- control change;
- pitch bend;
- tempo changes;
- running status;
- multiple tracks for format-1 files.

The parser is deliberately platform-neutral. Saturn playback is a later consumer of the same normalized MIDI events, which also makes the event vocabulary reusable by Mjolnir and the flight recorder.

## Audio observatory direction

The flight recorder should evolve from raw register traffic toward normalized events such as:

```text
SOUND_RAM_LOAD
SLOT_KEY_ON
SLOT_KEY_OFF
SLOT_SOURCE_CHANGE
SEQUENCE_START
SEQUENCE_STOP
MIDI_BANK
MIDI_PROGRAM
MIDI_NOTE_ON
MIDI_NOTE_OFF
PCM_STREAM_START
PCM_STREAM_STOP
CDDA_PLAY
CDDA_PAUSE
CDDA_STOP
MIXER_CHANGE
DSP_EFFECT_CHANGE
```

Where evidence allows, each event should retain:

- frame/timestamp;
- originating path/CPU;
- slot/channel/track;
- source address, disc identity or file fingerprint;
- pitch, pan and volume;
- loop/length information;
- correlation with currently observed text/scene state.

This is intended to support both reverse engineering and localization. SRK should be able to distinguish, for example, a CD-DA voice track from streamed PCM, a preloaded sample bank, or a sequence-driven sound before proposing a replacement strategy.

## Localization/replacement direction

Future replacement tooling should classify discovered audio into at least:

- CD-DA track;
- streamed PCM or another stream format;
- preloaded PCM sample/bank;
- sequence plus tone/sample bank;
- synthesized/effect-only event.

Replacement must preserve source-image immutability and validate the constraints relevant to the detected class, including format, sample width/rate, endianness, loop points, memory footprint, alignment, stream buffering, sequence/bank IDs, disc layout/LBA requirements and timing where the title depends on it.

This provides the foundation for multilingual voice replacements and for closed-caption timing derived from observed voice-start/voice-stop events.

## Public diagnostic distribution

The current Stage 6B research build links private Sega SBL objects. That is acceptable for local evidence gathering but must not automatically become a public downloadable binary.

Before a public release, every required runtime path should be reviewed for redistribution. Where necessary, proprietary-library-backed research paths should be replaced by SRK-owned or clearly redistributable implementations. Private Sega headers/libraries remain outside the repository and outside public source bundles.

## Implementation sequence

The next audio work should proceed in small independently testable layers:

1. platform-neutral Standard MIDI File parsing and normalized sequence events;
2. SCSP sample/slot completeness tests;
3. deterministic 68EC000 command path;
4. Saturn MIDI-file/sequence playback using the normalized parser output;
5. streaming PCM;
6. DSP/effect routing;
7. CD-DA playback and mixing;
8. bounded RAM/polyphony/stress tests;
9. flight-recorder audio-event observation;
10. replacement/caption correlation tooling.

Physical hardware remains the authority for each Saturn-facing stage. External MIDI hardware is not required.
