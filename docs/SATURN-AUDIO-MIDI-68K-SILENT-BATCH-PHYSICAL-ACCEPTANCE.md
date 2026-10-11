# Saturn MIDI / MC68EC000 Silent 27-Record Physical Acceptance

## Status

R19 is physically accepted on real Sega Saturn hardware.

The deployed candidate executed the complete reviewed silent 27-record SRKM batch on the Saturn sound CPU and produced the exact terminal acknowledgement required by the R19 contract.

```text
R19 PHYSICAL ACCEPTANCE : PASS
REAL SATURN HARDWARE    : PASS
SAROO EXECUTION         : PASS
FULL 27-RECORD BATCH    : PASS
MC68EC000 EXECUTION     : PASS
MAILBOX STATUS          : ACKNOWLEDGED
BOUNDARY                : PASS
FLAGS                   : 0x0001
READ_SEQUENCE           : 1
READ_INDEX              : 27
LAST_ERROR              : 0
MIDI-DRIVEN SCSP NOTE   : NOT ENABLED
```

The captured terminal screen also reported one poll and:

```text
Success: sequence=1 index=27 error=0
```

## Physical evidence

Physical capture supplied from the real Saturn:

```text
Capture filename : SRK-DIAG(8).mp4
Bytes            : 4956241
Duration         : approximately 23.833333 seconds
SHA-256          : 84c8e4ab6e8f75722fb3499244285607cb73e652b02e863742fdbc7aeba52d79
```

The capture visibly shows the `MIDI / 68K BATCH PROOF` screen reaching `ACKNOWLEDGED` / `PASS`, with READY flags `0x0001`, sequence `1`, index `27`, and error `0`.

The proof remains intentionally silent. No MIDI-driven SCSP note path is enabled in R19, and no distinct MIDI-generated note was observed in the capture.

The video itself is physical-validation evidence and is not committed to the repository; its SHA-256 records the reviewed artifact without adding a large binary validation file to source control.

## Candidate provenance

The physically accepted candidate project was:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R19-MIDI-68K-SILENT-BATCH-CANDIDATE-GATE1
```

Accepted provenance anchors:

```text
Candidate manifest:
04e873d537e5bd4a4ae7b6703abb35e112723724472b6418c9b5a8a57d0d8be8

Candidate build report:
78e7cfaaf9a70d6f71f905e0db807797c5102ec101bc333b2cde70f5cd447008

MC68EC000 batch image:
d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5

Deployable BIN:
8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34

Deployable CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The accepted MC68EC000 image geometry remains:

```text
Program address : 0x00004000
Stack           : 0x0007FFF0
Word count      : 5066
Byte count      : 10132
Program end     : 0x00006794
Records         : 27
```

## Guarded media provenance

R19 was deployed through the two-phase whole-card guard.

Prepare manifest:

```text
C:\Users\Developer.ERIDU\SRK-Workspace\R19-MIDI-68K-SILENT-BATCH-CARD-BEFORE.json
```

Prepare manifest SHA-256:

```text
7cef0c4d5d22ceea521864c283ca4b0108c8db78d0ba6a2357ee203372429582
```

Pre-write verification matched the complete card exactly. Post-write verification accepted only:

```text
saroo/ISO/TEST/SRK-Diagnostics-R19
saroo/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.bin
saroo/ISO/TEST/SRK-Diagnostics-R19/SRK-Diagnostics.cue
```

The deployed BIN/CUE hashes matched the accepted build artifacts, and existing SAROO content was not overwritten or removed.

## What R19 proves

R19 closes the complete fixed-batch silent execution chain on physical hardware:

```text
SH-2 producer
-> complete 27-record canonical SRKM preload
-> Saturn Sound RAM
-> installed resident MC68EC000 image at 0x00004000
-> real MC68EC000 execution
-> validation of all 27 records
-> reviewed state publication
-> mailbox acknowledgement
-> SH-2 observation of READ_INDEX = 27
```

Because the resident image publishes its reviewed state before writing the final acknowledgement, `READ_INDEX = 27` is downstream of the complete fixed-batch validation/state-publication path.

## What R19 deliberately does not prove

R19 is not yet the final MIDI player. It does not establish:

- a general dynamic resident MIDI decoder loop;
- arbitrary-length command consumption;
- real-time event scheduling;
- voice allocation;
- SCSP MIDI-generated notes;
- polyphony;
- multi-channel rendered music;
- tone-bank/program mapping for arbitrary files.

Those remain separate gates.

## Baseline policy

R17 remains the recovery baseline.

R18 remains the accepted one-record real-Saturn MIDI/MC68EC000 round-trip baseline.

R19 is now the accepted full fixed-batch silent MC68EC000 baseline.

All three are immutable historical anchors. Future driver work must create new gates rather than rewriting these accepted artifacts.

## Next direction

With fixed-batch physical execution proven, the next engineering stage is the general resident decoder:

```text
dynamic command loop / indexed queue consumption
-> arbitrary MIDI-derived command programs
-> timing/state proof
-> voice allocation
-> first MIDI-driven SCSP note
-> polyphony / multi-channel playback
```

Third-party CC0 MIDI files may now be added as source assets for this next stage, while preserving each original file byte-for-byte and keeping all derived outputs separate.

> Safer is secure, secure is faster.
