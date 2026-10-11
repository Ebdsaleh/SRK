# Saturn MIDI 68K Resident Decoder Physical Candidate Full-Build Gate

## Purpose

This gate derives a fresh off-card callable candidate for the post-R19 general
MC68EC000 resident decoder.  It starts only from the accepted inert full-build
tree and binds a deliberately non-R19 seven-record proof to the diagnostics UI.

The gate builds the candidate but does not deploy it.

## Accepted inert baseline

Expected project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-RESIDENT-DECODER-INERT-FULL-GATE1
```

Externally accepted inert media:

```text
BIN:
4861a1b1abb06e2d52a126f95f7f06727c359fcb5f81ec33058865221ecaa7b7

CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

Accepted decoder provenance:

```text
image:
d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4

compiler source:
2a05b422db80ce890e7e6a8b99b128e8606cca4abf8b56118b4ada8e6093bfb4

compiler header:
856f105d41e8e504d37ad0de815086c9f4546cfdbd48f029d7941d8e9afcf8b9

compiler object evidence:
e593b8506656fbd2f0e7117382b9de3e0e7642c79cff811c53251be06a620761

accepted inert runtime-after:
722ee1423162e31014c7a65f612c1efd09e0c81b368dabc988a3360a3bdf8d76
```

The baseline verifier also re-hashes every manifest-pinned generated input and
requires the current build report to match the current manifest.

## Candidate proof

The proof contains seven runtime records.  It is not the R19 27-record batch.
Every SRKM v1 opcode appears exactly once.

```text
1000 us  NOTE_OFF
2000 us  NOTE_ON
3000 us  POLY_AFTERTOUCH
4000 us  CONTROL_CHANGE
5000 us  PROGRAM_CHANGE
6000 us  CHANNEL_PRESSURE
7000 us  PITCH_BEND
```

Channels are `0..6` and all data bytes remain valid 7-bit MIDI values.

## Derived tree

The accepted inert tree is never modified.

A fresh staging tree is created from verified generated inputs.  Only the copied
candidate sources are transformed.

The copied R19 main/menu are changed to:

```text
#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1
menu: MIDI 68K Decoder Proof
expected read index: 7
```

The release-A / fresh-A interlock is retained.

The screen additionally exposes:

```text
Processed
Current
Decoder ready
```

## Generated seams

Eight generated C89 provenance files are written into the fresh candidate tree:

```text
srk_saturn_midi_68k_resident_decoder_installer.c/.h
srk_saturn_midi_68k_resident_decoder_proof_preload.c/.h
srk_saturn_midi_68k_resident_decoder_runtime.c/.h
srk_saturn_midi_68k_resident_decoder_physical_proof.c/.h
```

The four implementation sources are appended to the copied fixed-build runtime
translation unit.  The global standalone source list is not widened.

## Runtime begin sequence

The candidate reuses the physically accepted R19 hardware adapter for the SMPC
stop/start boundary:

```text
SNDOFF through accepted adapter
-> install and verify exact 239-word decoder at 0x4000
-> publish exact seven-record proof preload
-> verify exact preload
-> SNDON through accepted adapter
-> RUNNING
```

## PASS contract

Mailbox:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     7
LAST_ERROR     0
```

Decoder telemetry:

```text
magic          0x5244 (RD)
version        1
processed      7
current        7
final time     7000 us
ready          1
```

The runtime returns `ACKNOWLEDGED` only when both the mailbox and decoder
telemetry contracts pass.

## Build-time safety

The full-build gate records:

```text
decoder linked                    YES
decoder installed during build    NO
decoder executed during build     NO
decoder candidate bound           YES
MIDI-driven SCSP note attempted   NO
build-time SMPC commands          NO
build-time Sound-RAM writes       NO
build-time MC68EC000 execution    NO
SAROO write                       NO
off-card only                     YES
```

The candidate becomes behaviorally active only if a later separately reviewed
media deployment occurs and the user explicitly triggers the proof.

## ERIDU command

Use a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_resident_decoder_physical_candidate_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-RESIDENT-DECODER-INERT-FULL-GATE1" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R20-MIDI-68K-RESIDENT-DECODER-CANDIDATE-GATE1" ^
  --expected-baseline-bin-sha256 4861a1b1abb06e2d52a126f95f7f06727c359fcb5f81ec33058865221ecaa7b7 ^
  --expected-baseline-cue-sha256 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950 ^
  --expected-image-sha256 d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4 ^
  --expected-compiler-source-sha256 2a05b422db80ce890e7e6a8b99b128e8606cca4abf8b56118b4ada8e6093bfb4 ^
  --expected-compiler-header-sha256 856f105d41e8e504d37ad0de815086c9f4546cfdbd48f029d7941d8e9afcf8b9 ^
  --expected-compiler-object-sha256 e593b8506656fbd2f0e7117382b9de3e0e7642c79cff811c53251be06a620761 ^
  --expected-runtime-after-sha256 722ee1423162e31014c7a65f612c1efd09e0c81b368dabc988a3360a3bdf8d76
```

## Expected successful boundary

```text
Proof records           : 7
Proof final time        : 7000 us
Proof opcode coverage   : all 7 SRKM v1 opcodes exactly once
Proof screen            : MIDI 68K Decoder Proof
Trigger                 : release A, then fresh A press
Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 7 / error 0
Decoder telemetry       : RD v1 / processed 7 / current 7 / ready 1
MIDI-driven SCSP note   : NO
Build-time hardware I/O : NO
SAROO writes            : NONE
Result                  : SUCCESS
```

## Stop boundary

Do not deploy the candidate after this command.

The next tranche must independently re-open the completed candidate and verify
its manifest/report, source hashes, seven-record binding, MODE1 media, and exact
BIN/CUE hashes before any SAROO write path is designed.
