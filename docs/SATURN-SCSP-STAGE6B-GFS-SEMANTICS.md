# Saturn SCSP Stage 6B — GFS Runtime Semantics

## Status

Stage 6B Gate 4 is the first complete successful off-card build of the packaged
PCM runtime path. The Python-native build compiled all SRK sources, assembled
startup, linked the mixed ELF/COFF Sega SBL closure, packaged the ISO, verified
`/SRKPCM.BIN;1`, and emitted a verified MODE1/2352 BIN/CUE image without any
SAROO/card write.

The remaining pre-R17 semantic gate is now closed against Sega's File System
Library documentation and the installed SBL 6.01 header contract.

## Exact GFS contracts used by SRK

The Stage 6B loader intentionally uses only the simple synchronous high-level
GFS path:

```text
GFS_Init
GFS_NameToId
GFS_Open
GFS_GetFileSize
GFS_Close
GFS_Load
```

The installed SBL 6.01 declarations are:

```c
Sint32 GFS_Init(Sint32 open_max, void *work, GfsDirTbl *dirtbl);
Sint32 GFS_NameToId(Sint8 *fname);
GfsHn GFS_Open(Sint32 fid);
void GFS_Close(GfsHn gfs);
void GFS_GetFileSize(GfsHn gfs, Sint32 *sctsz, Sint32 *nsct, Sint32 *lstsz);
Sint32 GFS_Load(Sint32 fid, Sint32 ofs, void *buf, Sint32 bsize);
```

SRK relies on the following documented semantics.

### `GFS_Init`

The function value is the number of directory entries read. A negative value is
an error code. Therefore Stage 6B treats only `result < 0` as initialization
failure; a non-negative directory count is success.

`GFS_Init` also performs the file-system initialization and CD mount operation,
so the bounded proof does not add a speculative second CDC initialization.

### `GFS_Open`

The function value is a file handle. `NULL` is returned on error. Stage 6B
therefore treats only a null handle as open failure.

### `GFS_GetFileSize`

The outputs are:

```text
sctsz  = sector length in bytes
nsct   = sector count including the final sector
lstsz  = number of file-data bytes used in the final sector
```

The documented byte size is:

```text
file_size = sctsz * (nsct - 1) + lstsz
```

Stage 6B uses this exact equation and requires the result to equal the pinned
`SRKPCM.BIN` size of 1040 bytes before any load is accepted.

The mixed Form1/Form2 special case is irrelevant to this Stage 6 proof because
`SRKPCM.BIN` is a normal ISO9660 file in the generated MODE1 image.

### `GFS_Load`

`GFS_Load` returns the number of bytes actually read and returns a negative
error code on failure. Its `off` argument is in sectors, while `bsize` is the
maximum byte count. The destination must be 4-byte aligned.

Stage 6B requests exactly 1040 bytes at sector offset zero into a `Uint32`
backed buffer and accepts the load only when the function value is exactly
1040. The SRKP header and every payload field are then validated before sample
words are exposed to the accepted SCSP path.

## Current SRK implementation check

The already-built Gate 4 source matches all four contracts:

```text
GFS_Init        -> failure only when result < 0
GFS_Open        -> failure only when handle == NULL
GFS_GetFileSize -> (nsct - 1) * sctsz + lstsz
GFS_Load        -> success only when return == 1040 bytes
```

No runtime behavior change is required by this semantic review.

## Next gate

The remaining source change before R17 is presentation-only:

- update the Audio / SCSP screen from Stages 1-5 to Stages 1-6;
- expose the existing `DOWN+Y` packaged/disc-PCM chord in the on-screen legend;
- retain all accepted Stage 1-5 controls and telemetry unchanged.

After that source gate is green, create a fresh guarded R17 candidate and prove
on Saturn hardware:

```text
DOWN+Y -> ISO /SRKPCM.BIN -> Sega GFS -> bounded WRAM validation
       -> SRK Sound RAM -> accepted single-slot SCSP playback
```

R16 remains the physical recovery baseline until R17 passes.
