# Saturn MIDI 68K R23 Inert Audio Full-Build Gate

R22A is the immutable real-hardware baseline for SRK's resident Saturn MIDI
stream/scheduler.  R23 advances that work toward the first MIDI-driven SCSP
note, but the new resident audio image must first survive a full standalone
integration without being installed or executed.

This gate is deliberately **inert**.  It answers a narrow question: can the
compiler-accepted R23 resident image coexist with the exact accepted R22A
standalone project and pass the normal Saturn build without changing the
already-callable R22A proof or performing hardware I/O?

## Accepted baseline

The only reviewed input is the exact R22A physical candidate project.  The gate
requires caller-supplied SHA-256 anchors for its:

- project manifest;
- successful build report;
- deployable BIN and CUE;
- runtime source;
- main source;
- menu source;
- corrected R22A physical-proof source and header; and
- already-linked stream producer source and header.

The baseline manifest is also inspected semantically.  It must still describe
the 40-record, 32+8 R22A scheduler proof with the accepted timing/refill and
1408-word state-verification contract.

## R23 compiler anchors

The gate independently regenerates the R23 resident audio image and requires
exact hashes from the accepted legacy compiler gate for:

- resident image;
- resident source;
- resident header;
- voice-state header;
- producer source;
- producer header;
- accepted resident object evidence; and
- accepted producer object evidence.

The object hashes are provenance evidence.  The inert standalone build does not
install or execute those objects as an MC68EC000 runtime.

## Fresh-tree policy

The output path must not already exist.  Only files listed in the accepted
R22A generated-file inventory are copied to a temporary staging tree.  Before
publication every copied file is rechecked by size and SHA-256.

The gate then adds only these R23 generated files:

```text
src/srk_saturn_midi_68k_resident_audio_service.c
src/srk_saturn_midi_68k_resident_audio_service.h
src/srk_saturn_midi_68k_voice_state.h
```

The SH-2 stream producer is already linked in the R22A runtime, so it is not
injected a second time.

The accepted R22A main and menu are copied byte-for-byte and remain the callable
candidate binding.  The R23 resident audio array is appended to the runtime
translation unit solely so the ordinary standalone compiler/linker sees it.

## Inert boundary

A successful R23 inert full build proves:

```text
R22A main/menu binding        : preserved
R22A queue/refill semantics   : preserved
R22A timestamp scheduler      : preserved
R22A MIDI-state semantics     : preserved
R23 resident audio image      : linked
R23 voice-state contract      : linked
R23 SCSP-capable instructions : present in inert image
R23 resident installed        : no
R23 resident executed         : no
R23 candidate bound           : no
MIDI-driven SCSP note run     : no
build-time hardware I/O       : no
SAROO writes                  : none
```

The presence of SCSP-access instructions in generated constant image data is
intentional.  Build-time execution of those instructions is forbidden.

## R23 first-note contract carried forward

The inert image is the source/compiler-approved monophonic proof image:

```text
0 us        NOTE_ON  channel 3  note 60  velocity 100
1000000 us  NOTE_OFF channel 3  note 60
```

Its bounded ownership remains:

```text
0x2000-0x20FF  deterministic PCM waveform
0x2100-0x21FF  voice allocation state/telemetry
0x2200-0x22FF  128-note SCSP pitch table
slot 0         only owned SCSP voice
voice stealing disabled
```

The inert gate does **not** claim that this note has been heard or that SCSP
registers have been touched.  Those are physical-candidate requirements.

## Non-goals

This gate does not:

- modify R22A;
- write to SAROO;
- install the R23 image in Sound RAM;
- start or reset the sound CPU;
- execute SCSP MMIO;
- emit an audible note;
- prove polyphony or voice stealing; or
- select the final hardware-derived MIDI timebase.

## Promotion rule

Only after the inert full build succeeds and its fresh manifest/report/media
hashes are recorded may R23 advance to a separate callable physical candidate.
That later candidate must retain independent pre-media and whole-card guarded
deployment before any SAROO write.

Physical R23 acceptance is stricter than earlier silent milestones: telemetry
alone is insufficient.  The bounded Note On must be audibly produced by the
real Saturn and the scheduled Note Off must terminate it while the accompanying
voice/slot state verifies correctly.

> Safer is secure, secure is faster.
