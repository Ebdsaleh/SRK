# Saturn audio — Sega Sound I/F Direct MIDI backend

## Status

This is the replacement **musical playback backend** for the R26-R28 synthetic
SCSP timbre path.

R26-R28 remain accepted engineering evidence for:

- SRK MIDI parsing and deterministic scheduling;
- the 9,154-record / 287-batch Space Spectre transport;
- SH-2 <-> MC68EC000 communication;
- SCSP hardware diagnostics and observer/flight-recorder work.

They are not the required high-fidelity renderer.

## Sega Sound Driver boundary

The Sega Sound I/F Library documents Direct MIDI control as:

```c
SndRet SND_CtrlDirMidi(
    SndSeqNum seq_no,
    SndSeqPri seq_pri,
    Uint8 md_com,
    Uint8 ch,
    Uint8 dt1,
    Uint8 dt2
);
```

The Direct MIDI channel-message command values used by SRK are:

| `md_com` | MIDI meaning |
| ---: | --- |
| 0 | Note Off |
| 1 | Note On |
| 2 | Polyphonic Aftertouch |
| 3 | Control Change |
| 4 | Program Change |
| 5 | Channel Pressure |
| 6 | Pitch Wheel |
| 7 | System Message |

SRKM v1 already carries the first seven channel-message classes.  SRK therefore
does not need to reinterpret the music to use this backend: it converts each
scheduled SRKM record to the corresponding Direct MIDI call while preserving
its timestamp, channel and two MIDI data bytes.

## Percussion rule

The Space Spectre source uses MIDI percussion channel 10 (zero-based channel 9)
and the observed drum notes are:

- 35
- 40
- 42
- 51

The Direct MIDI adapter forwards all four note numbers unchanged.

It does **not**:

- repitch one generic drum waveform;
- replace the drum kit with generated noise;
- collapse the four notes into one percussion family;
- mute the percussion channel;
- modify note velocity to hide a source/backend mismatch.

Drum/instrument identity belongs to the **loaded Sega tone bank**.  A proper
General-MIDI-capable tone bank therefore supplies the actual kick, snare,
hi-hat and cymbal samples/voice definitions selected by those notes.

## Tone-bank policy

SRK must not commit Sega/DTS proprietary tone-bank data.

The hardware build will bind an explicit local tone-bank asset supplied by the
installed/owned Sega development environment, record its path/size/SHA-256 in
build provenance, and copy it only into the fresh generated test candidate when
required by the Sega Sound Driver loading flow.

No synthetic fallback is permitted for a candidate presented as the real
musical fidelity test.  If the required local tone bank is unavailable, the
build must stop and say which asset is missing.

## C adapter

The standalone integration contains a deliberately thin boundary:

```text
srk_saturn_sbl_direct_midi(...)
    -> SND_CtrlDirMidi(...)
```

It contains no Sound-RAM address, SCSP register programming, KYON sequencing,
voice allocator or synthetic timbre generator.  Those responsibilities belong
to Sega's Sound Driver and its loaded tone data for this backend.

## First compiler acceptance

Before this adapter is linked into a Saturn candidate, the Eridu compiler gate
must compile it against the **installed `sega_snd.h`** using the same legacy
SH-ELF GCC policy as the standalone project.

The compiler gate also fingerprints the selected installed `sega_snd.a`, but it
does not link it yet.  Link closure is the next implementation step after the
exact header/API compile is physically accepted on Eridu.

No generic SDK discovery report is required for this step.

## CD-DA

CD-DA is a parallel completion track, not something that waits behind another
round of synthetic MIDI timbre work.  Its implementation must use the documented
CDC/Sound-I/F calls and preserve the already-defined requirements for play,
pause/resume, stop/end-of-play handling, track/position control, level, pan and
mixing.
