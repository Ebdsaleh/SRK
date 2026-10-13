# Saturn Audio / MIDI 68K R26 — Double Impact multi-instrument source engine

R26 returns SRK to the real-music milestone after the narrow R25 release-tail
calibration.

The first target is the exact CC0 Double Impact member:

```text
midis/E1M2, E4M3 - Matzu - Space Spectre.mid
SHA-256 984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01
```

The source is decoded in memory from the repository's five hash-locked base64
transport chunks. It is never rewritten.

## R26 audio direction

R26 reuses the accepted R25 scheduler, seven-opcode resident MIDI state decoder,
FRT-compatible timestamp contract and release lifecycle.

The new source engine adds:

- 16 owned SCSP voices for the first Double Impact target;
- eight deterministic Saturn-native melodic PCM timbres selected by GM
  16-program family;
- a separate channel-10 percussion timbre;
- exact real-SMF profiling, including channels, program changes, controllers,
  percussion notes, tempo count and raw polyphony;
- a capacity simulation that includes the R25 120-ms release-ownership tail.

This timbre bank is deliberately synthetic and copyright-clean. It is an
audible multi-instrument bring-up bank, **not** a claim of General MIDI
soundfont/SC-55 fidelity.

The source gate fails if the selected track cannot fit the 16-voice
non-stealing policy. That prevents a physical candidate from silently dropping
notes.

## Read-only profile command

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r26_double_impact_profile ^
  --repository-root "C:\Users\Developer.ERIDU\repos\Python\SRK" ^
  --release-rate 16
```

This command writes neither the repository source assets nor the SAROO card.
Its output is the evidence used to lock the first physical R26 candidate.
