# Saturn Audio — Silent MIDI MC68EC000 Candidate Pre-Media Gate

## Purpose

This gate is the independent checkpoint between a successful callable R18
off-card build and any later SAROO write.

It does **not** trust the prior build command merely because that command printed
`SUCCESS`.  It re-opens the completed candidate as an external artifact and
revalidates the evidence from disk.

It also does not deploy anything.

## Independent evidence boundary

The gate requires:

```text
completed candidate project
mounted SAROO card root
fresh destination name
existing category, when used
externally accepted deployable BIN SHA-256
externally accepted deployable CUE SHA-256
```

The expected BIN/CUE hashes come from the independently observed successful
candidate build output.  They are caller supplied deliberately so a later
modified build report cannot silently redefine which image was accepted.

## Candidate manifest verification

The gate validates:

```text
standalone-project schema/mode
complete generated-file inventory
unique generated-file paths
size of every generated input
SHA-256 of every generated input
presence of candidate main/menu
presence of physical-proof source/header
```

It then requires the exact R18 candidate contract:

```text
candidate define                         enabled
candidate screen                         MIDI 68K Silent Proof
physical proof linked                    true
proof UI compiled                        true
proof call path compiled                 true
proof called during build                false
user trigger required                    true
trigger                                  A
release-after-screen-entry interlock     true
polling                                  at most once/frame while RUNNING
success sequence                         1
success index                            1
success error                            0
MIDI-driven SCSP note attempted          false
build-time SMPC commands                 false
build-time Sound-RAM writes              false
build-time MC68EC000 execution           false
SAROO write                              false
off-card only                            true
```

The policy record must independently preserve the corresponding no-action state.

## Source-level binding verification

The candidate main is re-read from disk and must still contain the reviewed:

```text
physical-proof begin call
physical-proof non-blocking poll call
A-release arming check
fresh A-press trigger check
exact success telemetry text
```

The candidate menu must expose:

```text
MIDI 68K Silent Proof
```

and must not retain the old placeholder label.

The fresh candidate main/menu/proof source/proof header SHA-256 values must match
the hashes pinned by the candidate manifest.

## Build-report binding

The completed build report must be:

```text
schema     srk.saturn.standalone-build.v1
successful true
```

and its recorded project-manifest SHA-256 must equal the freshly calculated
candidate manifest SHA-256.

This prevents a modified candidate source tree from being paired with an older
successful build report.

## Reuse of the generic SAROO planner

After candidate-specific verification passes, this gate delegates to SRK's
existing read-only standalone SAROO deployment planner.

That planner independently:

```text
revalidates deployable BIN/CUE against the build report
requires the exact single-track CUE contract
freshly verifies MODE1/2352 BIN against the intermediate ISO
validates the mounted card as modern SAROO
requires SAROO/ISO
requires any requested category to already exist
refuses an existing destination
refuses an existing pending deployment directory
```

The resulting fresh BIN/CUE SHA-256 values must then equal the caller-supplied
externally accepted hashes.

## No write path

The pre-media module imports only:

```text
plan_saroo_standalone_image_deployment
```

It does not import or call:

```text
apply_saroo_standalone_image_deployment
```

The CLI contains no:

```text
--apply
--confirm
```

A passing result therefore performs no SAROO write.

## CLI

```text
python -m rikai_kotoba.tools.saturn_midi_68k_physical_proof_candidate_pre_media_gate \
  --project <completed-r18-candidate> \
  --card-root <mounted-saroo-card> \
  --category TEST \
  --name SRK-Diagnostics-R18 \
  --expected-bin-sha256 <accepted-bin-sha256> \
  --expected-cue-sha256 <accepted-cue-sha256>
```

Expected terminal state:

```text
Proof UI/call path       : VERIFIED
Trigger interlock        : VERIFIED
Fresh MODE1 verification : PASS
Candidate provenance     : PASS
Externally accepted hash : PASS
SAROO destination        : FRESH
SAROO writes             : NONE
Result                   : PRE-MEDIA GATE PASS
```

## Gate order after PASS

A pre-media PASS is still not a physical proof result.  It means the exact
accepted image has been revalidated and has a safe fresh SAROO destination.

Next:

1. create the final guarded R18 deployment instruction using the already
   established whole-card guard/verification workflow;
2. write only the new `SRK-Diagnostics-R18` directory;
3. verify the entire card against the pre-write inventory, allowing only that
   exact new BIN/CUE directory;
4. safely eject and boot the real Saturn;
5. enter `MIDI 68K Silent Proof`;
6. release A;
7. press A once;
8. accept only:

```text
ACKNOWLEDGED
READ_SEQUENCE = 1
READ_INDEX    = 1
LAST_ERROR    = 0
```

No MIDI-driven SCSP note is attempted before this silent round trip is accepted.

> Safer is secure, secure is faster.
