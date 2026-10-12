# Saturn Audio/MIDI — R24 Real-SMF Compiler + Inert Integration Gate

## Status

R23 is the immutable physical first-audio baseline. R24 advances from one
synthetic proof note to playback of an actual Standard MIDI File while retaining
all existing provenance and card-safety rules.

This gate is **off-card only**. It does not create a deployable R24 physical
candidate and must not be copied to SAROO.

## Reference song

R24 uses the existing CC0 source without modifying it:

```text
assets/midi/cc0/melody-town-theme/Melody Town Theme.mid
SHA-256: 9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041
```

Reviewed contract:

```text
SMF format       1
Tracks           3
PPQN             96
Tempo            845070 us/quarter
SRKM records     310
Duration         108151354 us
Note On          140
Note Off         140
Control Change   23
Program Change   3
Pitch Bend       4
Note range       71..86
Peak polyphony   2
Queue batches    32+32+32+32+32+32+32+32+32+22
```

The four Pitch Bend records in this exact source are all center-position events.
The song's relevant initial mixer state is volume 100 and pan 64. Therefore the
first R24 physical song proof does not require dynamic bend-to-SCSP pitch
modulation or pan changes to reproduce this source's note pitches and centre
placement.

The source carries program 73. R24 preserves Program Change as MIDI state but
does **not** claim General-MIDI flute synthesis. The first real-song milestone
uses SRK's calibrated loop waveform to prove melody, timing, pitch placement,
refill continuity and two-voice overlap. Timbre/program-bank synthesis remains a
later sound-engine capability.

## R24 resident audio memory ownership

```text
0x2000  physically proven 100-sample PCM loop
0x2100  historical R23 voice block; not R24 truth
0x2200  calibrated R24 128-note OCT/FNS table
0x2300  R24 two-slot voice ledger (0x100 bytes)
0x2400  R24 128-entry velocity/mixer table (0x100 bytes)
0x2500  end of R24 audio-owned data
...
0x4000  resident MC68EC000 program
```

R24 owns SCSP slots 0 and 1 only. Allocation is deterministic lowest-free-slot,
matching notes retrigger their owner, and no stealing is permitted. A third
simultaneous note reports BUSY. The exact reference song models to peak two
voices, 140 successful key-ons, 140 key-offs, zero busy errors and zero active
voices at completion.

## Scheduler-register liveness

The resident service is derived from the physically accepted R23 scheduler.
`D2:D3` remain live as the current 32-bit record timestamp until
`stream_record_done` publishes the due-time telemetry.

R24 peak-polyphony telemetry therefore uses scratch `D4`; it must never borrow
`D2` or `D3`. A dedicated regression locks this invariant.

## Pitch calibration

R23 deliberately used diagnostic `note 60 -> pitch 0`, which made the proven
100-sample loop sound near 441 Hz. R24 instead treats that loop as a 441 Hz base
at SCSP pitch zero and selects the nearest OCT/FNS multiplier for each equal-
tempered MIDI target relative to A4=440 Hz.

The host model requires quantisation error below one cent over MIDI 0..127.

## Physical clock boundary

The complete-song player consumes only monotonic microseconds. It does not know
which hardware timer produced them.

R24 includes a Saturn SH-2 FRT backend renderer with:

```text
FRC_H  0xFFFFFE12
FRC_L  0xFFFFFE13
TCR    0xFFFFFE16
mode   /128
```

The backend extends 16-bit wraps and converts elapsed ticks using an explicit
caller-supplied `source_hz`. No PAL/NTSC/source-clock frequency is guessed in
this gate. Rendering and compiling the backend performs no FRT access; hardware
reads occur only if a later physical candidate calls it.

## Legacy compiler gate

`midi_68k_r24_compile_probe.py` renders and compiles four independent C units
with the installed legacy SH-ELF GCC:

1. R24 resident MC68EC000 constant image,
2. accepted SH-2 stream/refill helper,
3. complete 310-event real-song producer,
4. SH-2 FRT clock backend.

Compiler flags remain:

```text
-Wall -Werror -m2 -O0 -ffreestanding -fno-builtin
```

The probe does not link, build an ISO, install the resident image, execute SCSP
or FRT MMIO, write Sound RAM, or touch SAROO.

## Inert standalone full-build gate

`midi_68k_r24_inert_full_build_gate.py` derives a **fresh** project from the
exact physically accepted R23 candidate. It independently requires:

- exact R23 manifest and successful build-report SHA-256,
- report-to-manifest pairing,
- exact accepted deploy BIN/CUE hashes,
- full generated-file inventory verification,
- accepted R23 resident image and generated representation hashes,
- accepted R23 physical proof source/header hashes,
- intact R23 main/menu/runtime gate binding.

Only manifest-tracked generated inputs are copied. R24 source representations
are added to the fresh tree and injected into the fixed standalone runtime
translation unit so the normal compiler/linker/ISO pipeline must accept them.
The R23 main/menu/callable physical proof are not changed.

The R24 manifest explicitly records:

```text
accepted R23 candidate binding preserved : true
R24 resident linked as constant data      : true
R24 resident installed                    : false
R24 resident executed                     : false
R24 player linked                         : true
R24 player invoked                        : false
R24 FRT backend linked                    : true
R24 FRT backend invoked                   : false
physical clock frequency selected         : false
SCSP MMIO executed                        : false
Sound RAM writes                          : false
FRT MMIO executed                         : false
build-time hardware I/O                   : false
SAROO write                               : false
off-card only                             : true
behaviorally active                       : false
```

A successful inert full build is evidence for the next physical-candidate
tranche. It is **not deployable R24 media**.

## Next gate after acceptance

After Eridu accepts both the legacy compiler probe and the inert standalone
build, R24 may advance to a fresh physical candidate that:

1. explicitly selects/calibrates the Saturn hardware time source,
2. installs the new two-slot resident image,
3. streams all ten real-song batches,
4. proves four genuine two-note overlap entries,
5. reaches all 310 records and sequence 10,
6. reports 140 key-ons / 140 key-offs / peak active 2 / busy 0 / active 0,
7. plays the recognisable ~108-second reference melody,
8. goes through the normal independent pre-media, whole-card PREPARE and guarded
   APPLY sequence before any SAROO write.

R23 remains immutable throughout.
