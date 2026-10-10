# Saturn SCSP Diagnostic — Stage 6B Packaged PCM Runtime Proof

Stage 6A proved that SRK can generate `SRKPCM.BIN`, package it into the Saturn ISO, reopen that ISO, and verify the exact payload bytes before BIN/CUE publication.

Stage 6B closes the remaining Audio/SCSP integration gap by making the Saturn itself read that packaged file and route its validated sample payload through the already physically accepted SCSP path.

## Scope

The Stage 6B proof is deliberately bounded:

```text
ISO /SRKPCM.BIN
        |
        v
Sega GFS root lookup + synchronous load
        |
        v
4-byte-aligned bounded WRAM buffer
        |
        v
strict SRKP v1 validation
        |
        v
new SRK-owned Sound-RAM region
        |
        v
existing accepted single-slot SCSP path
```

This stage does **not** introduce streaming, WAV parsing, CDDA, DSP effects, arbitrary file loading, or title-resident coexistence.

## Evidence basis

Runtime access is based on the user's installed SBL 6.01 material and the preceding read-only evidence gate, not guessed CD-block commands.

The chosen private build dependencies remain outside the public SRK repository and outside generated project trees:

- `SEGA_GFS.H`
- ELF `sega_gfs.a`
- ELF `SEGA_CDC.A`

Fresh project manifests pin their absolute path, size, and SHA-256. The Python-native builder verifies those fingerprints before and after each build, adds only the installed include directory to compilation, and links the two pinned archives by exact path.

`GFS_Init` owns the documented filesystem/CD mounting initialization for this simple proof. Stage 6B does not issue an additional guessed CDC initialization sequence.

## File contract

`SRKPCM.BIN` remains the Stage 6A format:

```text
magic        SRKP
version      1
encoding     signed PCM16 big-endian
channels     1
samples      512
loop start   0
loop end     511
file bytes   1040
```

The runtime loader requires the exact file size and validates every header field before exposing any samples to the audio backend.

The synchronous path is:

```text
GFS_Init
GFS_NameToId("SRKPCM.BIN")
GFS_Open
GFS_GetFileSize
GFS_Close
GFS_Load
```

The GFS destination is backed by 32-bit storage so the caller buffer is 4-byte aligned.

## SCSP ownership

Stage 6B adds one new SRK-owned Sound-RAM source:

```text
byte address  0x00002800
samples       512 file-backed PCM16 words
LSA           0
LEA           512
```

The package's logical final sample index is 511. As with the already accepted Stage 1/4 loop convention, Sound RAM also receives one explicit endpoint sample at index 512 copied from loop start.

No accepted SCSP constants change:

- MID pitch remains `0x0000`;
- center/left/right DIPAN mappings are unchanged;
- direct-send volume encoding is unchanged;
- KYONB/KYONEX handling is unchanged;
- Sound CPU lifecycle is unchanged.

## Diagnostic control

Stage 6 uses the remaining explicit mode chord:

```text
DOWN+Y -> toggle packaged/disc PCM mode
```

The chord has priority over ordinary `Y = MID` selection.

Entry establishes:

- single-slot mode;
- MID pitch;
- CENTER pan;
- default volume 4;
- playing;
- unmuted;
- packaged waveform ID 2.

Ordinary play/mute/pan/pitch/volume controls remain available while active. Exiting returns to a stopped normal tone state.

The backend attempts the GFS load at most once while one packaged-mode entry remains active. A failed attempt returns `Host submit: NO` and leaves the owned voices silent. Leaving the mode permits one fresh retry. A successful validated payload remains resident for the lifetime of that standalone diagnostic run.

## Safety gates

Before any R17 card write:

1. ERIDU source tests must be green at the exact Stage 6B source HEAD.
2. A fresh off-card generated project must compile/link with the real local SH-ELF toolchain and pinned SBL libraries.
3. The real build must again prove `/SRKPCM.BIN` identity inside the ISO.
4. Any unresolved symbol, compiler error, GFS dependency mismatch, or packaging mismatch stops the process.
5. Only after that artifact proof may a fresh guarded R17 candidate be created.

R16 remains the physically accepted recovery baseline until R17 passes on Saturn hardware.

## Planned R17 physical acceptance

The decisive proof is:

1. boot R17 and enter Audio / SCSP Test;
2. reconfirm a brief Stage 1-5 regression;
3. press simultaneous `DOWN+Y`;
4. require `Host submit: OK`;
5. require file-backed source telemetry:
   - slot 0 source `0x2800`;
   - slot 0 LEA `0x0200`;
   - MID pitch `0x0000`;
6. hear the deterministic packaged waveform from the expected single-slot CENTER path;
7. verify A, C, LEFT/UP/RIGHT, X/Y/Z and L/R remain responsive;
8. exit `DOWN+Y`, then verify ordinary square-source playback still works;
9. repeat entry/exit with no stale source, stuck note, hang, or failed re-entry;
10. START must silence owned audio and return cleanly with no resume/leakage;
11. Input, Video and VDP1 regressions remain intact.

If R17 passes, the current Audio/SCSP diagnostics phase is complete. More advanced audio features are deferred until a later feature actually requires them.
