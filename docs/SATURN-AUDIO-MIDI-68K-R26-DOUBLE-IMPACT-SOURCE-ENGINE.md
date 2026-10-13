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

The source engine adds:

- 16 owned SCSP voices for the first Double Impact target;
- eight deterministic Saturn-native melodic PCM timbres selected by GM
  16-program family;
- a separate channel-10 percussion timbre;
- exact real-SMF profiling, including channels, program changes, controllers,
  percussion notes, tempo count and raw polyphony;
- a capacity simulation that includes the R25 120-ms release-ownership tail;
- R26-local long-safe MC68EC000 branches so the larger 16-voice image does not
  alter the accepted R23-R25 assembler output.

This timbre bank is deliberately synthetic and copyright-clean. It is an
audible multi-instrument bring-up bank, **not** a claim of General MIDI
soundfont/SC-55 fidelity.

## Real-song pressure result and allocation policy

The first Eridu R26 run proved Space Spectre reaches:

```text
peak HELD voices     10
peak owned voices    16
non-stealing BUSY    12
```

The important distinction is that the musical held-note peak is only 10. The
12 failed Note Ons happened because already-decaying R25 release tails still
owned the remaining slots.

R26 therefore keeps the 16-slot target and changes only the pressure fallback:

1. matching channel/note retrigger;
2. lowest free slot;
3. lowest releasing slot, cancelling that tail;
4. BUSY only if all 16 owned slots are still HELD.

The source model must report those 12 old pressure points as release-tail
steals and zero BUSY allocations. New Note Ons are preserved instead of being
silently dropped.

## R26-local long-safe branch encoding

The original four-slot R25 image uses signed 16-bit Bcc/BRA displacements. The
first 16-slot R26 build exceeded that range (`error_sequence` was 34,468 bytes
away). R26 does not change the accepted shared assembler. Its local assembler
emits:

```text
BRA -> JMP (xxx).L
Bcc -> B!cc.s +6 ; JMP (xxx).L
```

The MC68EC000 supports absolute-long JMP. The temporary assembler substitution
is scoped to R26 image generation and is restored afterwards together with all
R25 globals/callbacks.

## Read-only profile command

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r26_double_impact_profile ^
  --repository-root "C:\Users\Developer.ERIDU\repos\Python\SRK" ^
  --release-rate 16
```

This command writes neither the repository source assets nor the SAROO card.
Its output is the evidence used to lock the first physical R26 candidate.
