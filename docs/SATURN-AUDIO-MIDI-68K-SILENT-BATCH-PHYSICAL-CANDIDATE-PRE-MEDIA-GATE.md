# Saturn Audio / MIDI 68K — R19 Silent Batch Physical Candidate Pre-Media Gate

## Purpose

This gate independently re-opens the completed R19 callable silent 27-record
MIDI/MC68EC000 candidate before any deployment is allowed.

It is deliberately read-only with respect to the mounted SAROO card.

## Accepted incoming evidence

The R19 candidate full-build gate must already have completed successfully.
The externally accepted anchors for the first R19 candidate are:

```text
MC68EC000 batch image SHA-256:
d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5

R19 deployable BIN SHA-256:
8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34

R19 deployable CUE SHA-256:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The candidate build remains silent:

```text
ACKNOWLEDGED / sequence 1 / index 27 / error 0
MIDI-driven SCSP note: NO
```

## Independent checks

The pre-media gate re-opens the candidate from disk and verifies:

1. Standalone manifest schema and mode.
2. Every manifest-pinned generated file by size and SHA-256.
3. Inherited inert full-build provenance and the exact compiler-accepted batch image hash.
4. R19 physical-candidate manifest schema and policy.
5. Candidate `main.c` starts with the R19 compile-time candidate define.
6. The diagnostics binding still expects index 27.
7. Release-A then fresh-A trigger interlock remains present.
8. Candidate menu still exposes `MIDI 68K Batch Proof` only at the isolated placeholder.
9. Installer, batch runtime, proof header and injected runtime hashes still match the candidate manifest.
10. Build report is successful and bound to the current manifest hash.
11. Existing standalone deployment planner independently re-verifies BIN/CUE/MODE1 packaging.
12. Fresh BIN and CUE hashes exactly match the externally accepted build output.
13. Destination is fresh according to the existing read-only SAROO planner.

## Write boundary

This gate imports only:

```text
plan_saroo_standalone_image_deployment
```

It does not import or call an apply function.

It has no confirmation token, no copy operation and no deployment mode.

Therefore:

```text
SAROO writes: NONE
```

## First R19 pre-media command

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_silent_batch_physical_candidate_pre_media_gate ^
  --project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R19-MIDI-68K-SILENT-BATCH-CANDIDATE-GATE1" ^
  --card-root D:\ ^
  --category TEST ^
  --name SRK-Diagnostics-R19 ^
  --expected-image-sha256 d31773d8f2d2119618b353ce5b6f7e05f892636d3d69c564531b3de1c4c485b5 ^
  --expected-bin-sha256 8bdbb66f9d7be28b520424d6d0d5b957a999722c17695ca80fe773a82e73dd34 ^
  --expected-cue-sha256 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The expected terminal boundary is:

```text
Proof UI/call path      : VERIFIED
Trigger interlock       : VERIFIED (release A, then fresh A press)
Silent PASS contract    : ACKNOWLEDGED / sequence 1 / index 27 / error 0
MIDI-driven SCSP note   : NO
Fresh MODE1 verification: PASS
Candidate provenance    : PASS
Batch image provenance  : PASS
Externally accepted hash: PASS
SAROO destination       : FRESH
SAROO writes            : NONE
Result                  : PRE-MEDIA GATE PASS
```

## After PASS

A PASS does **not** authorize manual copying or generic deployment.

The next tranche must add a dedicated two-phase R19 guarded deployment using a
fresh off-card whole-card inventory manifest, an R19-specific confirmation
token, exact allowed paths and safe rollback rules equivalent to or stronger
than the accepted R18 deployment guard.

R17 and R18 remain recovery baselines and must not be overwritten.
