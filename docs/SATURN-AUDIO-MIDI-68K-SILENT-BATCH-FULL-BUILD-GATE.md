# Saturn Audio — Silent Full-Batch MC68EC000 Full-Build Gate

## Purpose

R18 physically proved the one-record SH-2/Sound-RAM/MC68EC000 round trip.
The next silent 27-record program has separately passed its source model,
machine-word interpreter tests, and legacy SH-ELF compiler probe.

This gate asks one narrower question:

```text
Can the complete standalone Saturn diagnostic carry the reviewed
10,132-byte / 5,066-word full-batch MC68EC000 image without changing the
accepted R18 binding or executing the new program?
```

The answer must be established off-card before any new physical candidate is
created.

## Accepted inputs

The gate requires three independent SHA-256 values on its command line.

Accepted R18 callable-candidate project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R18-MIDI-68K-SILENT-CANDIDATE-GATE1
```

Accepted R18 manifest:

```text
4b195b8ddffd73bb488504ea1f31fbcaece96d6dc071dd57d62d7f3a3893f33b
```

Accepted R18 build report:

```text
000206ad62cb6925c76a37c5c40bef8c5c892ac44734ae133d3cf0274f47b5c1
```

Accepted silent full-batch image from the real compiler gate:

```text
d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5
```

The build gate refuses to derive from a different manifest, build report or
regenerated batch image.

## R18 is immutable

The gate copies only the manifest-pinned generated inputs from the accepted R18
candidate into a fresh off-card tree.

It preserves the existing R18 candidate `main.c` and diagnostic menu unchanged.
The R18 one-record proof remains the only callable MIDI/68K binding in this
intermediate image.

The new batch program is not selected by reset vectors and is not callable.

## Integration method

`standalone_build.py` intentionally has a fixed reviewed C-source set.  To prove
link integration without widening that global build policy, the new constant
program definition is appended to the copied `srk_saturn_runtime.c` under an
explicit marker.  A standalone source/header copy is also retained in the
fresh project for provenance and hash inspection.

The derived manifest records both runtime hashes:

```text
runtime_before_sha256
runtime_after_sha256
```

and pins the generated program source/header independently.

## Batch program contract

```text
program start : 0x00004000
word count    : 5066
byte size     : 10132
program end   : 0x00006794
records       : 27
queue words   : 108
```

The new image remains silent and has no SCSP voice-write path.

## Required inert state

The manifest must record:

```text
existing R18 binding preserved    YES
batch program present             YES
batch program linked              YES
batch program installed           NO
batch program executed            NO
batch candidate bound             NO
MIDI-driven SCSP note attempted   NO
build-time SMPC commands          NO
build-time Sound-RAM writes       NO
build-time MC68EC000 execution    NO
SAROO write                       NO
behaviorally active               NO
```

This means the new program exists in the built binary but cannot execute from
this gate.

## Source regression gate

Before running the real standalone build, the repository test suite must remain
green.  The new tests verify:

```text
fresh derivation does not mutate R18
R18 main/menu remain byte-identical
batch source/header/runtime injection are inventory-pinned
program geometry and hash metadata remain exact
batch is linked but uninstalled/unbound/unexecuted
baseline manifest/report hash mismatch is rejected
batch-image hash mismatch is rejected
baseline generated-input tampering is rejected
existing output directory is refused
no card/deployment dependency exists
```

## Full-build command

After the source suite is green, run:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_silent_batch_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R18-MIDI-68K-SILENT-CANDIDATE-GATE1" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-SILENT-BATCH-INERT-FULL-GATE1" ^
  --expected-baseline-manifest-sha256 4b195b8ddffd73bb488504ea1f31fbcaece96d6dc071dd57d62d7f3a3893f33b ^
  --expected-baseline-report-sha256 000206ad62cb6925c76a37c5c40bef8c5c892ac44734ae133d3cf0274f47b5c1 ^
  --expected-image-sha256 d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5
```

The output directory must be fresh.

## Expected successful boundary

The CLI must report:

```text
R18 manifest SHA-256   : 4b195b8d...
R18 report SHA-256     : 000206ad...
Batch image SHA-256    : d31773d8...
Batch image words      : 5066
Batch image bytes      : 10132
Program range          : 0x00004000-0x00006794
Expected records       : 27
Existing R18 binding   : PRESERVED
Batch program linked   : YES
Batch program installed: NO
Batch program executed : NO
Batch candidate bound  : NO
MIDI-driven SCSP note  : NO
Build-time hardware I/O: NO
SAROO writes           : NONE
Result                 : SUCCESS
```

All compile/assemble/link/ISO/package commands must return zero and the generated
artifacts/report must be preserved for review.

## This command does not authorize deployment

Do not copy this image to SAROO.

Do not modify R18.

Do not execute the new 27-record image on Saturn from this gate.

A successful full build only authorizes the next design step: a separate new
candidate binding that explicitly installs the `0x4000` program, expects
`READ_INDEX = 27`, exposes the expanded telemetry, and remains silent.

That later candidate will receive its own source gate, full build, independent
pre-media gate, whole-card guarded deployment and real-hardware acceptance.

> Safer is secure, secure is faster. <3
