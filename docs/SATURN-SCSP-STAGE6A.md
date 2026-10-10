# Saturn SCSP Diagnostic — Stage 6A Packaged PCM Provenance

Stage 6A is the first step away from synthetic/in-memory-only audio generation.

It deliberately stops **before Saturn runtime CD/file reading**. Its job is to prove that one deterministic SRK-owned PCM payload can be generated, pinned, packaged into the fresh diagnostics ISO, reopened independently, and verified byte-for-byte before the BIN/CUE candidate is published.

## Goal

Establish a trustworthy file-backed input artifact without changing the physically accepted Stage 1-5 SCSP hardware path.

Stage 6A proves:

1. a deterministic PCM payload is generated into the fresh standalone project;
2. the project manifest pins its exact size and SHA-256;
3. `mkisofs` packages it as an ISO-9660 root file;
4. SRK reopens the generated ISO through its existing read-only `DiscImage` + `ISO9660Reader` stack;
5. the ISO file extent is read back and compared byte-for-byte against the generated project payload;
6. its ISO extent LBA, size, SHA-256 and loop metadata are recorded in the build report;
7. any mismatch stops the build before MODE1/2352 BIN/CUE publication.

No SD-card write or physical R17 candidate belongs to Stage 6A by itself.

## Payload filename

```text
SRKPCM.BIN
```

The file is created under:

```text
cd/SRKPCM.BIN
```

The existing ISO builder packages the complete `cd` tree, so the file becomes an ISO root entry alongside the executable.

## SRK packaged PCM v1

The first payload uses a deliberately tiny SRK-owned format rather than WAV or a proprietary Sega container:

```text
Offset  Size  Meaning
0x00    4     magic "SRKP"
0x04    1     version = 1
0x05    1     encoding = 1 (signed PCM16 big-endian)
0x06    1     channels = 1 (mono)
0x07    1     reserved = 0
0x08    4     sample_count, big-endian
0x0C    2     loop_start, big-endian
0x0E    2     loop_end, big-endian
0x10    ...   signed PCM16 big-endian sample data
```

The initial deterministic payload contains:

```text
sample_count = 512
loop_start   = 0
loop_end     = 511
channels     = 1
encoding     = signed PCM16 big-endian
```

Thirty-two fixed signed levels are each repeated for sixteen samples. The first and final levels are zero. The pattern is deterministic and intentionally makes no calibrated sample-rate or acoustic claim.

## Project-generation provenance

`prepare_saturn_standalone_project()` writes the payload only inside the fresh temporary project tree before atomic publication.

The generated project manifest records:

- relative payload path;
- format version;
- encoding identity;
- channel count;
- sample count;
- loop start/end;
- byte size;
- SHA-256.

The payload is also part of the existing `generated_files` inventory, so the normal generated-input verification catches any pre-build or post-build mutation.

The installed Saturn SDK, reviewed template and source IP.BIN remain read-only.

## ISO verification

After `mkisofs` returns success, but before MODE1/2352 BIN/CUE publication, the builder:

1. opens `build/srk_diag.iso` read-only with `DiscImage`;
2. opens its ISO-9660 filesystem with `ISO9660Reader`;
3. resolves `/SRKPCM.BIN` case-insensitively;
4. records the actual ISO extent LBA;
5. reads exactly the file extent bytes;
6. requires exact byte equality with `cd/SRKPCM.BIN`;
7. requires the expected SHA-256;
8. reparses the packaged PCM header and loop contract.

If any step fails, the build is unsuccessful and the deployable BIN/CUE directory is not published.

## Build-report contract

A successful `SRK_STANDALONE_BUILD.json` gains:

```text
packaged_pcm.project_path
packaged_pcm.iso_path
packaged_pcm.iso_extent_lba
packaged_pcm.size
packaged_pcm.sha256
packaged_pcm.sample_count
packaged_pcm.loop_start
packaged_pcm.loop_end
packaged_pcm.verified_against_project = true
```

`cd/SRKPCM.BIN` is also listed as a build artifact alongside the executable, ISO, map, copied `0.bin`, and deployable BIN/CUE.

## Safety boundary

Stage 6A does **not**:

- read the file from Saturn hardware;
- issue CD block commands;
- link or copy proprietary Sega filesystem libraries into SRK;
- change SMPC commands;
- change SCSP pitch/pan/key/direct-send constants;
- write new PCM data to Sound RAM at runtime;
- add WAV parsing;
- stream audio;
- deploy a new SAROO candidate.

R16 remains the physically accepted baseline while Stage 6A is validated off-card.

## Stage 6A acceptance gates

Before Stage 6B starts:

1. the full Python source gate must pass;
2. a fresh off-card standalone project must contain deterministic `cd/SRKPCM.BIN` with its manifest hash;
3. a real-toolchain build must succeed;
4. the build report must show the ISO extent and exact packaged payload SHA-256;
5. independently reading the generated ISO through SRK must return the same bytes;
6. no SD-card write occurs.

Only then should Stage 6B implement Saturn-side loading/playback, using supplied Sega documentation and known-good local examples as authority for the CD/filesystem path rather than guessing hardware commands.

## Stage 6A accepted artifact proof

Stage 6A passed its real-toolchain artifact gate on ERIDU and is **ACCEPTED**.

The fresh project was created at:

```text
C:\Users\Developer.ERIDU\SRK-Workspace\Stage6A-Artifact-20261010-01
```

Project preparation resolved the expected local `sh-elf-gcc`, `sh-elf-as`, and `mkisofs` tools while leaving the installed Saturn development trees and source `IP.BIN` read-only.

The real build completed every compile, assemble, link, ISO-package, packaged-PCM verification, and MODE1/2352 publication step with return code `0`.

The packaged file was observed inside the real ISO as:

```text
/SRKPCM.BIN;1
extent LBA 39
size       1040 bytes
SHA-256    d4b9e26d0e3b0e54085b6169c5c0fc784ec9c3f005bcbbda96529db443c07b39
```

The generated project manifest independently records the same payload as:

```text
path         cd/SRKPCM.BIN
version      1
encoding     pcm16-be-signed
channels     1
sample_count 512
loop_start   0
loop_end     511
size         1040
SHA-256      d4b9e26d0e3b0e54085b6169c5c0fc784ec9c3f005bcbbda96529db443c07b39
```

The build report records:

```text
iso_path                  /SRKPCM.BIN;1
iso_extent_lba            39
verified_against_project  true
```

An external Windows `certutil -hashfile ... SHA256` over the project payload produced the same SHA-256 value.

The successful deployable artifact remained off-card:

```text
BIN SHA-256  6f3614c4a298fc5001758a56862741ce65ad55416406c08e7e7cfa248fdf8f1b
CUE SHA-256  5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
MODE1        64 sectors / 150528 raw bytes
```

No BIN/CUE was copied to SAROO and no physical Saturn media was written during this gate.

Stage 6A therefore closes the host-side provenance chain from deterministic SRK-owned PCM bytes through real ISO packaging and read-back verification. Stage 6B may now begin, but its Saturn-side CD/filesystem implementation must first be grounded in the supplied Sega/SBL material and known-good local examples rather than guessed register-level CD commands.
