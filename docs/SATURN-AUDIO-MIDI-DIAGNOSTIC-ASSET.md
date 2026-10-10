# Saturn Audio MIDI Diagnostic Asset Contract

SRK's MIDI work now has a deterministic bridge between a real Standard MIDI
File and the future Saturn playback backend.

This tranche is still source-only. It does not change the standalone Saturn C
backend, generate a new hardware revision, or write to SAROO.

## Goals

The same authored sequence must be useful for three later consumers:

1. standalone Saturn audio diagnostics;
2. Mjolnir/audio inspection;
3. flight-recorder audio-event correlation.

External physical MIDI input is explicitly out of scope. The diagnostic target
is file/sequence playback on a standard Saturn.

## Canonical SMF asset

`formats.midi_diagnostic.build_srk_midi_diagnostic_bytes()` generates the test
asset from code. No external `.mid` file is required and no third-party musical
content is embedded.

The canonical file is:

```text
SMF format       1
tracks           3
PPQN             96
end tick         384
bytes            217
SHA-256          9b5356bf8413de26438711b7adfc1a8c6349c31f53448d8496caf24b5adfd9dc
```

The tracks are:

- conductor: track name + 500000 us/quarter tempo + a 400000 us/quarter change;
- melody: bank/program, volume, pan, three notes and a later program/pan change;
- harmony: bank/program, volume, pan, expression, two notes, pitch bend and
  sustain transitions.

This deliberately exercises normalized timing and channel state before any
SCSP-specific translation occurs.

## SRKM v1 compiled program

`hardware.saturn.midi_program.compile_saturn_midi_program()` consumes the
platform-neutral schedule and produces a Saturn-facing command program.

The serialized contract is big-endian:

```text
0x00  4   magic        "SRKM"
0x04  1   version      1
0x05  1   record size  8
0x06  2   reserved     0
0x08  4   event count
0x0C  4   duration us
0x10  ... records
```

Each 8-byte record is:

```text
+0  4  absolute time_us
+4  1  opcode
+5  1  MIDI channel 0..15
+6  1  data0
+7  1  data1
```

Opcodes:

```text
1 NOTE_OFF
2 NOTE_ON
3 POLY_AFTERTOUCH
4 CONTROL_CHANGE
5 PROGRAM_CHANGE
6 CHANNEL_PRESSURE
7 PITCH_BEND
```

Tempo/meta events are used to build the deterministic timeline but are not sent
as playback commands. SysEx remains preserved by the general SMF parser but is
rejected by SRKM v1 rather than silently discarded.

The canonical diagnostic currently compiles to:

```text
playback records 27
duration         1800000 us
serialized bytes 232
```

## C bridge

`render_saturn_midi_program_c()` renders the compiled schedule as a C89-friendly
constant `SRK_MIDI_PROGRAM_EVENT` array using only fixed integer fields.

This is intentionally still one step above the hardware backend. It does not
choose SCSP slots, waveform addresses, 68EC000 mailbox layout, or Sega sound
library calls.

The next hardware-facing tranche can therefore review those choices separately
without changing MIDI parsing/timing semantics.

## Safety and provenance

- the MIDI asset is generated deterministically from SRK-owned source;
- no proprietary Sega audio sequence or tone data is copied;
- no private SDK library is needed for this source-only stage;
- no installed SDK tree is modified;
- no SAROO/card write occurs;
- R17 remains unchanged.

## Next hardware bridge

After this source gate is accepted, proceed in small steps:

1. define an SRK-owned deterministic Saturn tone/sample bank;
2. define the SH-2 -> 68EC000 command mailbox;
3. add a bounded Saturn-side event queue consuming the generated C schedule;
4. prove one channel/note path first;
5. expand to program/bank/pan/volume/pitch/sustain semantics;
6. only then create a fresh hardware revision for guarded deployment.

This keeps the eventual MIDI-file playback proof separable from external MIDI
I/O and from any future virtual Saturn development-kit work.
