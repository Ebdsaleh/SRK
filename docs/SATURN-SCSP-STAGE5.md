# Saturn SCSP Diagnostic — Stage 5 Heterogeneous Dual-Source Pair

Stage 5 combines the two PCM regions already physically accepted in Stages 1-4 and plays them simultaneously through independent SCSP slots.

## Goal

Prove on real Saturn hardware that SRK can keep two owned SCSP slots active at the same time while each slot references a different Sound-RAM source.

This closes an important gap between the earlier proofs:

- Stage 2 proved two simultaneous slots, but both used the same square-wave Sound-RAM source.
- Stage 4 proved safe switching between the square and shaped PCM sources, but only on the single-slot path.
- Stage 5 proves independent per-slot SA/LSA/LEA source selection while both voices participate in one controlled pair.

This stage deliberately does **not** add filesystem loading, streaming, WAV parsing, CDDA, DSP effects, or new SCSP pitch/pan/key constants.

## Deterministic pair

Stage 5 uses:

```text
slot 0 / listener-left  = accepted square PCM source
                           Sound RAM 0x00002000
                           MID pitch
                           hard listener-left

slot 1 / listener-right = accepted shaped PCM source
                           Sound RAM 0x00002400
                           MID pitch
                           hard listener-right
```

Both voices use the same logical direct-send volume.

Using MID on both slots is intentional: physical isolation compares **timbre/source identity** without LOW/HIGH pitch being another variable.

## Control

`DOWN+Z` toggles the Stage 5 mixed-source pair.

On entry:

- pair mode becomes active;
- both voices are selected;
- volume resets to 4;
- playback starts;
- output is unmuted;
- Tone telemetry becomes `MIXED`;
- logical source label becomes `TONE+PCM`.

While active:

- `LEFT`: square source / listener-left only
- `RIGHT`: shaped PCM source / listener-right only
- `UP`: both sources
- `A`: Play / Stop
- `C`: Mute / Unmute
- `L` / `R`: shared volume down / up
- `DOWN+Z`: leave Stage 5 and return to a stopped single-slot tone state
- `START`: stop owned audio and return to diagnostics menu

`DOWN+Z` has priority over ordinary `Z = HIGH` tone selection on that controller sample.

The previously accepted explicit mode chords remain distinct:

- `DOWN+A`: Stage 2 same-source stereo pair
- `DOWN+B`: Stage 3 deterministic sweep
- `DOWN+C`: Stage 4 shaped single-slot source
- `DOWN+Z`: Stage 5 heterogeneous pair

## Per-slot source ownership

The standalone host now tracks source identity independently for the two owned slots:

```text
audio_waveform_id       = slot 0 source
audio_right_waveform_id = slot 1 source
```

Before either slot's source registers change, the backend checks whether the desired left/right source pair differs from the current pair.

If any owned voice is keyed and a source change is required:

1. execute a zero active-slot mask once;
2. mark the owned pair unkeyed;
3. retarget only the slot source(s) that changed;
4. continue through the normal desired-mask logic;
5. re-key only the voices requested by the current logical state.

This extends the physically accepted Stage 4 no-retarget-under-a-keyed-voice rule to both slots.

## Telemetry contract

The title-neutral host status retains the existing slot-0 aliases and adds raw observations for both owned slots:

- slot 0 control, source address, loop end, pitch, mixer;
- slot 1 control, source address, loop end, pitch, mixer.

For Stage 5 the expected source/loop values are:

```text
slot 0 source = 0x2000
slot 0 LEA    = 0x0064  (100)
slot 1 source = 0x2400
slot 1 LEA    = 0x0100  (256)
```

These values are backend observations only. Saturn addresses remain absent from the reusable diagnostic control core.

## R15 physical acceptance target

A fresh R15 candidate should prove:

1. R14 Stage 4 source switching still works before Stage 5 is entered.
2. `DOWN+Z` starts the mixed pair.
3. With `UP`/both selected:
   - listener-left carries the familiar square timbre;
   - listener-right carries the shaped PCM timbre;
   - both are audible simultaneously.
4. `LEFT` leaves only the square source on listener-left.
5. `RIGHT` leaves only the shaped source on listener-right.
6. `UP` restores both without changing their source identities.
7. `C` mute/unmute preserves pair selection.
8. `L`/`R` adjust both sources together.
9. `A` stops/resumes both sources cleanly.
10. `DOWN+Z` exits to a stopped single-slot tone state; pressing `A` then produces the original square source.
11. Repeat mixed-pair entry/exit several times with no stuck note, stale source, hang, or source swap.
12. `START` produces immediate silence and no leakage on menu return/re-entry.
13. Stage 2 stereo, Stage 3 sweep, Stage 4 shaped single-slot, Input, Video, and VDP1 remain stable.

Only after those observations should Stage 5 be physically accepted.
