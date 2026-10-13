# Saturn Audio / MIDI 68K R25 — RR16 Calibration Pre-Media Gate

This tranche independently re-opens the accepted R25 RR16 calibration build and proves that the exact candidate returned from Eridu is still safe to **plan** for SAROO media.

It contains no deployment/apply operation.

## Accepted Eridu checkpoint

Source HEAD that produced the candidate:

```text
e573a5bad7b655fb174f5e1e82e9814921e6861d
```

Validation returned from Eridu:

```text
focused R25 tranche       58 passed
unittest                  900 tests / OK
pytest -q                 912 passed, 34 subtests passed
pytest                     912 passed
full-build gate           SUCCESS
SAROO writes              NONE
```

Candidate:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R25-MIDI-RR16-CALIBRATION-FULL-GATE1
```

Accepted candidate anchors:

```text
manifest       5a282c2ea1077b95ca34bc1fd11593f34cef015baa6da1eb5c5cfe69f830cba9
build report   bcd65a3252e5b7980b2263b4134b8145405cbe043169bcbaacd196a1e708d991
R25 image      f11dd5559b5b1309922679f80fc8c36ed6cf8dc50a6b4073bdcdbaaeb3efe5e5
resident .c    a1b813a3a0ef01f07bbb18c77ff7c4df273fc7cd1cd9621398f583148bb86b2b
resident .h    c5ddca1488c7df0f4f8319a93720f93946b13be023b20ac7fd5a7ba4c6c4cceb
voice .h       c7a4e15cb83e0fcd76352cbb4ee9fe16e14a31985d30fd8ccff9e5742ec0d0b0
main           4116d997b7732295b1a8315827a75d44665d10e7f248deb219ff9188168bb976
menu           493788a27273ff4e4bd73c1ca3d0849fe8cd50486e08fa6e75880e5b489a064d
runtime        d936d2a0b6b7763224b29e8db10cce4be33e5115f36df21a189417e7df4cccf4
proof .h       d422ce6b48f0fea1e7eb342a1c8f73d14fd25980037f56159fa93430a866651f
proof .c       6b811165bcea3615da57144f0c3f81ac1d1c230c22ca5297820ec4bc275fe8be
BIN            a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71
CUE            5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
geometry       144 sectors / 338688 raw bytes / 294912 user bytes
```

## Independent checks

The pre-media gate:

1. verifies the exact accepted candidate manifest and build-report hashes;
2. verifies every manifest-tracked generated input on disk;
3. verifies the R25 gate still carries the physically accepted R24 provenance;
4. re-opens and hash-checks that exact R24 baseline;
5. re-renders the RR16 two-second calibration image, resident source/header, voice header and physical proof;
6. re-derives the R25 main/menu from the accepted R24 main/menu;
7. reconstructs the injected runtime byte-for-byte from the accepted R24 runtime plus the current accepted R25 renderers;
8. verifies the successful build-report/manifest pairing and no-write build policy;
9. verifies the accepted executable, ISO, map, deploy BIN/CUE and MODE1 geometry; and
10. calls only the existing read-only SAROO deployment planner, requiring a fresh destination.

The calibration semantics remain:

```text
RR                    16
EG1 / EG2             0x001F / 0x3C10
note                   A4 / MIDI 69 / velocity 100
Note On                250000 us
Note Off               1250000 us
observation window     2000000 us after Note Off
observation end        3250000 us
measurement            operator-observed audio
SCSP envelope readback unavailable
production RR          UNSET
```

## Read-only pre-media command

With the existing SAROO card mounted as `D:`:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r25_rr_calibration_pre_media_gate ^
  --project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R25-MIDI-RR16-CALIBRATION-FULL-GATE1" ^
  --card-root D:\ ^
  --category TEST ^
  --name "SRK-Diagnostics-R25-RR16-CAL"
```

Required terminal ending:

```text
Fresh MODE1 verification   : PASS
Externally accepted hashes : PASS
SAROO destination          : FRESH
SAROO writes               : NONE

Result                     : PRE-MEDIA GATE PASS
No SD-card files were modified. Do not deploy from this command.
```

## Stop point

A pre-media PASS is **not deployment authority**.

After the output is reviewed, the next tranche may prepare a whole-card guard for R25. The first whole-card action must be PREPARE/read-only only. No R25 write is authorised by this gate.
