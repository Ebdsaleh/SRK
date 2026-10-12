# Saturn Audio/MIDI — R24 Real-SMF Physical Candidate Gate

## Status

R23 remains the immutable first-audio physical baseline. The R24 source/model,
legacy compiler gate and inert full standalone integration have been accepted.

This tranche creates the first **callable** R24 real-song candidate, but the full
build command is still **off-card only**. A successful build is not permission to
copy anything to SAROO. Independent pre-media validation and a fresh whole-card
guard are required before any future write to the SD card.

## Accepted input baseline

The physical candidate derives only from the successful R24 inert project:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-INERT-FULL-GATE1
```

Accepted inert anchors include:

```text
deploy BIN
abb9f1c861380cbb80045d6c34aecd92c231db46b7554b0f53905d80ef01aa12

deploy CUE
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950

runtime after
after 783f02d8d11a483736633f79420d6c77b27f102c0295160b4409a62a8ce9294a

R24 resident image
e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e
```

The candidate gate verifies the inert manifest/report pairing, full generated
inventory, deploy artifacts and the exact accepted R24 resident/player/FRT
representation hashes before deriving a fresh tree.

## Real-song contract

Source remains the untouched CC0 file:

```text
assets/midi/cc0/melody-town-theme/Melody Town Theme.mid
SHA-256: 9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041
```

The physical proof requires:

```text
records             310
batches             10
batch sizes         32+32+32+32+32+32+32+32+32+22
final sequence      10
final read index    22
Note On             140
Note Off            140
peak active voices  2
busy allocations    0
final active voices 0
song duration       108151354 us
```

It also compares the complete accepted MIDI state representation at the end:

```text
channel summary words   256
controller words       1024
active-note words       128
                        ----
total                   1408 words
```

## Hardware time source

R22/R23 intentionally used an explicit producer-published synthetic
microsecond clock. R24 is the first song candidate to bind the player to a
Saturn-native clock.

The backend uses the master SH-2 free-running timer (FRT) in `/128` mode. The
proof does **not** hardcode one universal Saturn frequency. It reads the active
video standard and horizontal clock group at runtime:

```text
VDP2 TVSTAT bit 0 : 0 NTSC / 1 PAL
VDP2 TVMD HRESO0  : 0 graphic A / 1 graphic B
```

The corresponding Sega-documented SH-2 source clocks are:

```text
NTSC graphic A (320/640) : 26,874,100 Hz
NTSC graphic B (352/704) : 28,636,400 Hz
PAL  graphic A (320/640) : 26,687,700 Hz
PAL  graphic B (352/704) : 28,437,700 Hz
```

The proof saves the original FRT TCR before changing the clock-select field and
restores that original byte on every PASS or ERROR terminal path.

This gate establishes the implementation and compiler boundary. Actual timing
accuracy is not physically accepted until the later deployed candidate plays on
real Saturn hardware.

## Physical proof lifecycle

The explicit diagnostic screen remains A-triggered. Once triggered, the proof:

1. stops the sound CPU through the accepted hardware adapter,
2. clears the reviewed mailbox/service blocks,
3. copies and verifies the exact accepted R24 resident image in Sound RAM,
4. installs the MC68EC000 reset SSP/PC vectors,
5. starts the sound CPU,
6. waits for resident service magic/version,
7. detects the runtime Saturn clock group,
8. saves FRT TCR and configures `/128`,
9. resets the complete-song player at time zero,
10. publishes all ten queue batches as the resident acknowledges them,
11. samples/display-observes peak two-voice operation,
12. verifies the final 1408-word MIDI state and voice/refill counters,
13. restores FRT TCR,
14. publishes ACKNOWLEDGED only after every final contract passes.

A five-second margin beyond the reviewed song duration is a bounded timeout; it
is not part of the musical timing contract.

## Screen telemetry

The physical candidate screen exposes enough state to diagnose a real-hardware
failure without conflating transport, clock and audio errors:

```text
phase
records processed / batch count
clock microseconds / selected source Hz
read sequence / read index / published batch index
Note On / Note Off counts
active / peak / busy voice counts
polyphony observed
PAL flag / clock group B flag
state verifier status
resident voice error
```

The success string is:

```text
Song PASS: 310 events / peak voices 2
```

This is an objective machine-state success condition. Human recognition of the
~108-second melody remains additional physical evidence, not a substitute for
the counters and final state verifier.

## Build safety

The full-build gate may create a fresh candidate tree and normal Saturn BIN/CUE
artifacts, but during the command:

```text
resident installed on hardware : NO
resident executed               : NO
player invoked                   : NO
FRT MMIO                         : NO
SCSP MMIO                        : NO
Sound RAM hardware writes        : NO
SAROO writes                     : NONE
```

Candidate output path:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-R24-MIDI-REAL-SMF-PHYSICAL-CANDIDATE-GATE1
```

The directory must be fresh. Do not merge into, overwrite or repurpose the
accepted inert or R23 project trees.

## Stop point after a successful build

Record the fresh candidate manifest/report, main/menu/runtime/proof and deploy
BIN/CUE hashes. Then stop.

The next tranche is an **independent read-only pre-media gate**. Only after that
passes may a new whole-card PREPARE guard be taken. Only after that guard is
reviewed may an explicit guarded APPLY create a fresh
`SRK-Diagnostics-R24` directory on the SAROO card.

No manual copy is permitted.
