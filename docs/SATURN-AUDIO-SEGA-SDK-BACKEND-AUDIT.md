# Saturn Audio — Sega Sound SDK Backend Audit

## Purpose

R26-R28 established that SRK can transport and schedule the complete Space Spectre MIDI command stream through the Saturn sound CPU path. They did **not** establish General MIDI fidelity.

R28's physical result is therefore treated as a transport/driver proof, not as a fidelity baseline. Its synthetic percussion is not an acceptable implementation of the source MIDI's drum kit.

## Rule going forward

Do not ship another synthetic-percussion hardware candidate merely by tuning the R26-R28 generated waveforms.

For production-quality Saturn MIDI-style playback, first establish the exact interfaces that the user's installed Sega SBL/SGL sound stack provides for:

- sequence playback;
- tone/sample banks and maps;
- percussion/drum mapping;
- PCM playback/streaming;
- CD-DA playback/control.

The installed headers and Sega sample programs are the authority. SRK must not invent function names, command formats, bank layouts, or driver behavior when the SDK already defines them.

## R26-R28 role after the pivot

Keep the existing SRKM/MC68EC000 path because it has real value as:

- a known deterministic transport proof;
- a hardware/SCSP diagnostic reference;
- a future runtime observer/flight-recorder vocabulary;
- a fallback open implementation where appropriate.

Do not require that path to become the high-fidelity musical renderer merely because it was built first.

## Read-only installed-SDK probe

The repository now contains:

```text
python -m rikai_kotoba.tools.saturn_sound_sdk_probe --saturn-root <Saturn-Dev>
```

It reports, without modifying or executing the SDK:

- sound-related headers;
- `sega_snd` / `sega_pcm` / `sega_cdc` library artifacts by path, size and SHA-256;
- installed sound sample directories;
- exact source/header lines matching sequence/MIDI-style APIs;
- tone/bank/drum APIs;
- PCM APIs;
- CD/CD-DA APIs.

Private Sega code is not copied into SRK.

## Immediate engineering decision after evidence capture

1. If the installed Sega sound driver exposes a documented sequence + tone-bank path suitable for this workload, build the next playback backend on that documented path and feed it proper sample/tone-bank data including a real drum kit.
2. If it does not directly consume Standard MIDI, keep SRK's parser/scheduler as the conversion front-end and target the exact Sega sequence/bank format rather than synthesizing approximate SCSP timbres.
3. In parallel, close CD-DA using the documented installed CDC/SGL/SBL path rather than deferring it behind further synthetic MIDI experiments.

No instrument or percussion channel may be silently muted, replaced with a generic noise family, or simplified for hardware testing unless a diagnostic explicitly says that it is doing so.
