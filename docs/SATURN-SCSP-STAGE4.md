# Saturn SCSP Diagnostic — Stage 4 Deterministic Shaped PCM Source

Stage 4 advances from repeated square-wave tone control to a second deterministic in-memory PCM source while preserving the physically accepted Stage 1-3 SCSP path.

## Goal

Prove on real Saturn hardware that SRK can:

1. install more than one deterministic PCM region in Sound RAM;
2. retarget an owned SCSP slot between those regions;
3. preserve the accepted pitch, pan, volume, mute and key-control behavior with the alternate source;
4. switch sources without rewriting SA/LEA beneath a keyed voice.

This is deliberately **not** WAV parsing, filesystem streaming, CDDA, DSP effects, or title-resident sound coexistence. Those remain later stages.

## Source contract

Stage 1-3 tone source remains unchanged:

- Sound RAM byte address `0x00002000`;
- signed 16-bit square wave;
- normal loop;
- LSA `0`;
- LEA `100`.

Stage 4 installs a second deterministic source:

- Sound RAM byte address `0x00002400`;
- signed 16-bit shaped PCM contour;
- normal loop;
- LSA `0`;
- LEA `256`;
- loop endpoint explicitly returns to zero.

The shaped source contains 16 fixed signed levels. Each level is held for 16 samples, producing one 256-sample harmonic-rich contour. It is intended to be clearly distinguishable from the accepted square tone without depending on external media or a file decoder.

No calibrated frequency or musical-note claim is made.

## Control

`DOWN+C` toggles Stage 4 shaped-PCM mode.

On entry Stage 4 establishes:

- single-slot mode;
- shaped PCM source;
- CENTER pan;
- default volume 4;
- playing;
- unmuted;
- the most recently selected single-slot LOW/MID/HIGH pitch.

Unlike the Stage 3 automated sweep, Stage 4 deliberately leaves the accepted manual controls active:

- `A`: Play / Stop
- `C`: Mute / Unmute
- `LEFT` / `UP` / `RIGHT`: pan left / center / right
- `X` / `Y` / `Z`: LOW / MID / HIGH pitch selection
- `L` / `R`: volume down / up
- `DOWN+C`: leave shaped-PCM mode and return to a stopped tone-source state
- `START`: stop owned audio and return to the diagnostics menu

Ordinary `B` stereo toggling is suppressed while Stage 4 sample mode owns the source. Explicit mode chords still remain deterministic: `DOWN+A` can enter the accepted Stage 2 stereo-pair path, and `DOWN+B` can enter the accepted Stage 3 sweep path.

## Host boundary

The reusable diagnostics core now supplies a title-neutral `waveform_id` in `SRK_DIAG_AUDIO_REQUEST`.

The core owns only logical source identity:

- tone source;
- shaped PCM source.

The standalone Saturn backend owns:

- Sound RAM addresses;
- sample installation;
- SA/LSA/LEA programming;
- safe key-off before source retarget;
- re-key after source change;
- the already accepted pitch/mixer/pan encodings.

This keeps Saturn addresses out of the reusable diagnostic core and leaves room for a future resident host to implement logical source selection differently.

## Safe source switching

The backend tracks the currently selected waveform.

When a request changes source while an owned slot is keyed:

1. execute a zero active-slot mask;
2. record the owned slot as unkeyed;
3. update slot 0 SA/LSA/LEA to the requested deterministic Sound-RAM region;
4. continue through the normal desired-mask path;
5. re-key only if the logical request is still playing.

Stage 2 stereo mode forcibly uses the accepted tone source for both slots.

## R14 physical acceptance target

A fresh R14 candidate should prove:

1. R13 Stage 3 and R12 Stage 2 behavior remain intact.
2. In normal single-slot mode, play the accepted square tone at MID/CENTER/volume 4 as a comparison baseline.
3. Press `DOWN+C`:
   - playback remains controlled and stable;
   - the timbre changes clearly to the shaped PCM source;
   - pitch/pan/volume remain attributable to the existing logical controls.
4. `X`, `Y`, `Z` produce LOW/MID/HIGH relative pitch on the shaped source.
5. `LEFT`, `UP`, `RIGHT` preserve listener-left/center/listener-right behavior.
6. `L`/`R` adjust direct-send volume and `C` mutes/unmutes normally.
7. `A` stops and resumes the shaped source without leakage or corruption.
8. `DOWN+C` exits sample mode to a stopped tone-source state; pressing `A` again produces the original square-tone timbre.
9. Repeat source entry/exit several times with no crash, hang, stuck tone, or obvious state corruption.
10. `START` always silences owned audio and returns to the menu with no leakage.
11. Input, Video and VDP1 diagnostics remain stable, including accepted L=CCW / R=CW roll polarity.

Only after those observations should Stage 4 be physically accepted.
