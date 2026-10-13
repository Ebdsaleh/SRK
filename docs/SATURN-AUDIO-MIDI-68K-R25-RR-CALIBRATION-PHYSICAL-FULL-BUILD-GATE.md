# Saturn Audio / MIDI 68K R25 — RR Calibration Physical Full-Build Gate

This tranche derives a fresh **off-card** R25 release-rate calibration candidate from the exact R24 physical project that was accepted on Eridu and subsequently used for the successful R24 Saturn run.

It does **not** deploy anything to SAROO and it does **not** select a production RR.

## Accepted immutable R24 baseline

Project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-PHYSICAL-CANDIDATE-GATE1
```

Hard-pinned anchors:

```text
manifest  669d85db980f5c7922c5198dcc1b597b1d85664e543423f2c8570eeafa01fca6
report    d63adcd5e69cf4d96b6daac32c2acb06b6ce0d51ff3514d8802b96d9b6f21741
main      b4d6f25d3a39150061275a9ab701d3df32063cd0c73015eb9381c4fc7be5b45d
menu      7b36d84223c454999f3d2fecb7af2f17b368843f3dc24931dd1d958b92ad9e8e
runtime   ef8f0634ea018a247aac47b17a30fc043403849f0ea235e957db2708f7ebaed3
proof .h  80d9600baac43c0e19bb02c0de5010b904e2af27636eedff31bec124a7d9e918
proof .c  fda9c0e3993fd1e10ad6780b679a8c8d519b682d3bb07171c75ca19bf0709851
R24 image e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e
BIN       8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25
CUE       5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The gate also verifies every manifest-tracked R24 generated input before copying it. The R24 directory is read-only input and must remain byte-for-byte unchanged.

## First physical calibration probe

The first intended probe is explicitly RR16:

```text
RR                    16
EG1                   0x001F
EG2                   0x3C10
note                  A4 / MIDI 69
velocity              100
Note On               250000 us
Note Off              1250000 us
held duration         1000000 us
observation window    2000000 us after Note Off
observation end       3250000 us
records               2
batches               1
production RR         UNSET
```

The two-second value is the calibration-only slot-ownership boundary. It is not a claim that RR16 naturally lasts two seconds.

## Measurement boundary

The generated Saturn proof uses the physically accepted R24 SH-2 FRT /128 clock and runtime VDP2 clock-group selection. It displays machine timing and R25 release-ledger state while the operator listens to or records the physical audio.

The proof does not read or invent an SCSP envelope-level value. The SCSP slot monitor does not expose usable envelope level/phase readback for automatic silence detection.

## Fresh off-card command

The output directory must not already exist:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r25_rr_calibration_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-PHYSICAL-CANDIDATE-GATE1" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R25-MIDI-RR16-CALIBRATION-FULL-GATE1" ^
  --release-rate 16
```

Required policy output:

```text
Measurement mode             : OPERATOR-OBSERVED AUDIO
SCSP envelope readback       : NO
Production RR selected       : NO
Resident executed in build   : NO
FRT executed in build        : NO
SCSP MMIO in build           : NO
Build-time hardware I/O      : NO
SAROO writes                 : NONE
Result                       : SUCCESS
```

## Stop point

A successful build is evidence only. Do **not** copy the BIN/CUE to SAROO after this command.

After Eridu accepts the source/full-suite tests and this fresh full-build gate, the next tranche is an independent R25 pre-media verifier for the generated RR16 candidate. Only after that verifier passes may a guarded whole-card deployment be prepared.
