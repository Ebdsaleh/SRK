# Saturn MIDI / MC68EC000 Silent 27-Record Physical Candidate

## Status

This tranche follows the accepted inert full-build integration of the reviewed
silent full-batch MC68EC000 image.

The incoming evidence is:

- source suite: 578 pytest tests passed, plus 23 subtests;
- image SHA-256: `d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5`;
- inert deployable BIN SHA-256: `c0f935bef93e57109a56186171d2d357bbd9eadc783c0075cd2cbe10d77a5ef8`;
- inert deployable CUE SHA-256: `5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950`;
- batch program linked: yes;
- batch program installed/executed/bound: no;
- MIDI-driven SCSP note: no;
- SAROO writes: none.

R17 remains the recovery baseline and R18 remains the accepted one-record
real-Saturn MIDI/MC68EC000 round-trip baseline.

## Purpose

The next hardware question is deliberately narrow:

> Can the real Saturn MC68EC000 install the reviewed 0x4000 image, validate all
> 27 canonical SRKM records, publish the reviewed silent command state, and
> acknowledge the complete batch without generating audio?

This tranche prepares the callable candidate only.  The build command does not
run the Saturn hardware and cannot deploy to SAROO.

## Reused hardware surface

The candidate does **not** introduce a second SMPC implementation.

It reuses the R18 hardware adapter for:

1. SNDOFF;
2. publication and verification of the already-reviewed full 27-record preload;
3. SNDON;
4. mailbox reads.

The only substitution while the sound CPU is stopped is the new batch
installer.

## Batch installer

`srk_saturn_midi_68k_silent_batch_installer.c` copies the complete reviewed
image to Sound RAM at `0x00004000` and verifies every word.

Only after the image verifies does the installer publish:

- reset SSP: `0x0007FFF0`;
- reset PC: `0x00004000`.

This preserves the program-first / reset-vectors-last rule used by the accepted
R18 path.

## Runtime acceptance contract

The batch runtime is distinct from the R18 one-record runtime.

It accepts only:

```text
READY flag set
READ_SEQUENCE = 1
READ_INDEX    = 27
LAST_ERROR    = 0
```

Any non-zero `LAST_ERROR` is a consumer error.

The resident image also writes its detailed internal telemetry/state before it
publishes `READ_INDEX = 27`; therefore the public acknowledgement cannot occur
before the full queue validation and state publication complete.

## Guarded diagnostics binding

The repository main remains disabled by default.

The derived candidate alone prepends:

```c
#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1
```

The isolated diagnostics placeholder becomes:

```text
MIDI 68K Batch Proof
```

The screen retains the R18 input interlock:

1. enter the screen;
2. release A completely;
3. only a later fresh A press begins the attempt;
4. A is ignored while the proof is running;
5. a terminal result may be explicitly reset and rerun with a later fresh A.

Expected success text:

```text
ACKNOWLEDGED
sequence = 1
index    = 27
error    = 0
```

No MIDI-driven SCSP note is enabled.

## Candidate build provenance

The candidate builder accepts only a previously successful inert silent-batch
full-build tree.  It independently revalidates:

- the manifest/build-report relationship;
- every manifest-pinned generated input;
- the compiler-accepted batch image hash;
- the accepted inert BIN hash;
- the accepted inert CUE hash;
- linked-but-unbound/uninstalled/unexecuted batch state;
- no MIDI SCSP note;
- no build-time hardware action.

It then derives a fresh tree and hash-pins:

- reviewed and candidate main;
- reviewed and candidate menu;
- batch installer source/header;
- batch runtime source/header;
- shared proof header;
- batch-only proof-controller suffix;
- runtime before/after injection.

The accepted inert baseline is never edited.

## Build-time safety boundary

During candidate construction/build:

```text
Saturn hardware action       NO
SMPC command                 NO
Sound-RAM runtime write      NO
MC68EC000 execution          NO
MIDI-driven SCSP note        NO
SAROO/card write             NO
```

The normal standalone builder will still produce BIN/CUE artifacts.  Their
existence does not authorize deployment.

## Next gate after a successful candidate build

A successful candidate full build must be preserved and reviewed.  The next
tranche is an independent pre-media gate that revalidates candidate provenance,
MODE1 packaging, hashes, screen/call-path markers and the exact silent PASS
contract.

Only after that independent gate may a new guarded R19 SAROO deployment be
designed.
