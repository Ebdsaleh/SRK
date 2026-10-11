# Saturn MIDI — General MC68EC000 Resident Decoder Inert Full-Build Gate

## Purpose

R19 physically accepted the fixed silent 27-record batch proof.  The next
resident decoder removes that content dependency and has already passed its
host machine-word model plus the real legacy SH-ELF compiler gate.

This gate asks one deliberately narrower question:

> Can the exact compiler-accepted 239-word resident decoder be carried through
> SRK's complete standalone Saturn build while remaining impossible to install
> or execute through the new path?

This is an **off-card inert integration gate**.  It is not a physical candidate
and must not be deployed.

## Accepted inputs

The baseline is the exact physically accepted R19 candidate project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R19-MIDI-68K-SILENT-BATCH-CANDIDATE-GATE1
```

Externally accepted R19 anchors:

```text
manifest SHA-256:
04e873d537e5bd4a4ae7b6703abb35e112723724472b6418c9b5a8a57d0d8be8

build-report SHA-256:
78e7cfaaf9a70d6f71f905e0db807797c5102ec101bc333b2cde70f5cd447008

deployable BIN SHA-256:
8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34

deployable CUE SHA-256:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The accepted post-R19 decoder compiler evidence is:

```text
image SHA-256:
d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4

source SHA-256:
2a05b422db80ce890e7e6a8b99b128e8606cca4abf8b56118b4ada8e6093bfb4

header SHA-256:
856f105d41e8e504d37ad0de815086c9f4546cfdbd48f029d7941d8e9afcf8b9

legacy SH-ELF object SHA-256:
e593b8506656fbd2f0e7117382b9de3e0e7642c79cff811c53251be06a620761
```

The gate regenerates the decoder image/source/header and refuses to continue if
the image, source or header differs from those accepted values.  The object
hash is retained in the new manifest as external compiler evidence; the normal
standalone build recompiles the injected representation itself.

## Decoder geometry

```text
program address : 0x00004000
stack           : 0x0007FFF0
word count      : 239
byte size       : 478
program end     : 0x000041DE
runtime records : 1..32
embedded records: none
```

## R19 preservation

Before derivation the gate verifies:

- exact accepted R19 manifest hash;
- exact accepted R19 build-report hash;
- successful report/manifest relationship;
- every manifest-pinned generated input against disk;
- the R19 physical-candidate manifest contract;
- the R19 build-time no-hardware policy;
- exact accepted R19 deployable BIN and CUE hashes against both report and disk.

The derived tree copies only manifest-pinned generated inputs.

The existing R19:

```text
src/srk_saturn_main.c
src/srk_diag_menu.c
```

are not changed.  Therefore R19's accepted release-A/fresh-A proof path remains
the only callable MIDI/68K path in this intermediate tree.

## Link strategy

The standalone builder intentionally uses a fixed reviewed C-source list.  This
gate does not broaden that policy.

The exact generated decoder is preserved as standalone provenance files:

```text
src/srk_saturn_midi_68k_resident_decoder.c
src/srk_saturn_midi_68k_resident_decoder.h
```

and the same generated constant source is appended to:

```text
src/srk_saturn_runtime.c
```

under the unique marker:

```text
/* SRK MIDI 68K RESIDENT DECODER INERT FULL-BUILD GATE: constant image follows. */
```

This causes the final standalone linker to carry the decoder word array without
creating a new global source-discovery rule.

## Required inert state

The derived manifest records:

```text
existing R19 candidate binding preserved : yes
resident decoder present                  : yes
resident decoder linked                   : yes
resident decoder installed                : no
resident decoder executed                 : no
resident decoder candidate bound          : no
MIDI-driven SCSP note attempted           : no
build-time SMPC commands                  : no
build-time Sound-RAM writes               : no
build-time MC68EC000 execution            : no
SAROO write                               : no
off-card only                             : yes
new decoder behaviorally active           : no
```

## Real command

Use a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_resident_decoder_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R19-MIDI-68K-SILENT-BATCH-CANDIDATE-GATE1" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-RESIDENT-DECODER-INERT-FULL-GATE1" ^
  --expected-baseline-manifest-sha256 04e873d537e5bd4a4ae7b6703abb35e112723724472b6418c9b5a8a57d0d8be8 ^
  --expected-baseline-report-sha256 78e7cfaaf9a70d6f71f905e0db807797c5102ec101bc333b2cde70f5cd447008 ^
  --expected-baseline-bin-sha256 8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34 ^
  --expected-baseline-cue-sha256 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950 ^
  --expected-image-sha256 d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4 ^
  --expected-compiler-source-sha256 2a05b422db80ce890e7e6a8b99b128e8606cca4abf8b56118b4ada8e6093bfb4 ^
  --expected-compiler-header-sha256 856f105d41e8e504d37ad0de815086c9f4546cfdbd48f029d7941d8e9afcf8b9 ^
  --expected-compiler-object-sha256 e593b8506656fbd2f0e7117382b9de3e0e7642c79cff811c53251be06a620761
```

## Expected high-level result

```text
Existing R19 binding   : PRESERVED
Decoder linked         : YES
Decoder installed      : NO
Decoder executed       : NO
Decoder candidate bound: NO
MIDI-driven SCSP note  : NO
Build-time hardware I/O: NO
SAROO writes           : NONE
Result                 : SUCCESS
```

Capture the complete console output and every artifact hash from the successful
standalone build.

## Not authorised by this gate

Do not:

- deploy the emitted BIN/CUE;
- copy the tree to SAROO;
- install the 239-word image into Sound RAM;
- change reset vectors to the new decoder;
- execute the new decoder on the physical MC68EC000;
- claim dynamic MIDI state mutation;
- enable any MIDI-driven SCSP voice.

## Next gate

After an accepted inert full build, create a **fresh physical candidate** that
uses the same proven R19 hardware adapter but substitutes a new resident-decoder
installer/runtime contract.  Its first hardware mission remains silent and only
proves the newly introduced loop/pointer instruction path with a runtime-sized
batch.

Physical acceptance of that decoder-loop gate must occur before Phase B adds
dynamic channel/controller/note state mutation.

> R19 stays immutable; new behavior advances by new evidence.
