# Saturn SCSP Diagnostic — Stage 2 Stereo-Pair Proof

Stage 2 extends the physically accepted Stage 1 direct-PCM diagnostic without replacing its proven single-slot path.

## Goal

Prove that SRK can control two SCSP slots independently and simultaneously on real Saturn hardware while preserving the same title-neutral diagnostic boundary.

The Stage 2 stereo-pair mode uses two deliberately distinguishable voices:

- slot 0: LOW tone, hard listener-left;
- slot 1: HIGH tone, hard listener-right.

Both slots reuse the deterministic signed 16-bit square-wave sample already accepted in Stage 1. Pitch and direct-send pan distinguish the two voices.

## Controls

The Audio / SCSP diagnostic retains the Stage 1 controls and adds one mode toggle:

- `A`: Play / Stop
- `B`: toggle single-slot / stereo-pair mode
- `C`: Mute / Unmute
- `LEFT`: single mode = hard-left pan; stereo mode = left source only
- `UP`: single mode = center pan; stereo mode = both sources simultaneously
- `RIGHT`: single mode = hard-right pan; stereo mode = right source only
- `X`: select LOW single-slot tone
- `Y`: select MID single-slot tone
- `Z`: select HIGH single-slot tone
- `L`: volume down one step
- `R`: volume up one step
- `START`: stop owned audio and return to diagnostics menu

When stereo-pair mode is entered, the visible tone label becomes `STEREO` and the selection is reset to CENTER/BOTH. X/Y/Z continue to preselect the single-slot tone that will be restored when `B` returns to single mode.

## Slot ownership

Stage 2 owns only SCSP slots 0 and 1 in the standalone diagnostic image.

The backend keeps an explicit two-bit active-slot mask:

- bit 0 = slot 0 / left voice
- bit 1 = slot 1 / right voice

Changing LEFT/CENTER/RIGHT while playing updates that mask. The backend writes the desired KYONB state for both owned slots and then issues one KYONEX execution so key state changes occur as one reviewed operation.

Mute is intentionally different from Stop:

- Mute keeps the selected slots keyed while direct-send level becomes zero.
- Stop clears both owned slot mixers and executes a zero active-slot mask.

The bounded dummy MC68EC000 loop from Stage 1 remains running throughout.

## Physical acceptance for R11

R11 should prove:

1. Stage 1 single-slot behavior is unchanged.
2. `B` changes the dynamic tone label to `STEREO`.
3. With `A` playing and `UP` selected, LOW is heard only on listener-left while HIGH is heard only on listener-right at the same time.
4. `LEFT` leaves only the LOW left source audible.
5. `RIGHT` leaves only the HIGH right source audible.
6. Returning to `UP` restores both sources simultaneously.
7. `C` mutes/unmutes both without losing the selected source state.
8. `L`/`R` adjust both voices together.
9. `A` stops both voices.
10. `START` leaves no owned tone leaking into another diagnostic screen.
11. Returning with `B` to single-slot mode restores the preselected X/Y/Z tone and normal pan behavior.
12. Existing Input, Video and VDP1 diagnostics remain stable.

The already physically verified listener-left/listener-right DIPAN mapping is unchanged.
