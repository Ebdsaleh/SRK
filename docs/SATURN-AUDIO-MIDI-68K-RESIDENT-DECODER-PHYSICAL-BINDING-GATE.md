# Saturn MIDI / MC68EC000 Resident Decoder Physical Binding Gate

This gate prepares, but does not enable, the first real-hardware proof of the
post-R19 general resident decoder.

## Accepted incoming boundary

The exact 239-word Phase-A decoder has already passed source tests, the real
legacy SH-ELF compiler gate, and an inert full standalone build.

Accepted decoder identity:

```text
program address : 0x00004000
stack           : 0x0007FFF0
word count      : 239
byte size       : 478
program end     : 0x000041DE
image SHA-256   : d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4
```

Accepted inert standalone media:

```text
BIN SHA-256 : 4861a1b1abb06e2d52a126f95f7f06727c359fcb5f81ec33058865221ecaa7b7
CUE SHA-256 : 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

The inert image must not be deployed.

## Seven-record proof

The physical proof deliberately does not reuse R19's 27-record count.

It publishes seven runtime records with timestamps 1000 through 7000 us and
uses every SRKM v1 opcode exactly once:

```text
1 NOTE_OFF          channel 0
2 NOTE_ON           channel 1
3 POLY_AFTERTOUCH   channel 2
4 CONTROL_CHANGE    channel 3
5 PROGRAM_CHANGE    channel 4
6 CHANNEL_PRESSURE  channel 5
7 PITCH_BEND        channel 6
```

The proof therefore cannot be confused with R19's frozen unrolled batch.

## Preload publication

The generated proof preload:

1. withdraws READY;
2. writes exactly 28 queue words (7 records x 4 words);
3. publishes mailbox identity, write sequence, write index and queue count;
4. clears read sequence/index/error;
5. publishes READY last;
6. can read back and verify the exact queue and mailbox before SNDON.

No tone-bank or SCSP programming is required for this silent proof.

## Installer

The generated installer preserves the already accepted ordering:

```text
copy all 239 decoder words
-> write reset SSP = 0x0007FFF0
-> write reset PC  = 0x00004000
-> verify vectors + every decoder word
```

The installer never issues SNDON/SNDOFF itself.

## Runtime PASS contract

The runtime reuses the physically accepted R19 hardware-adapter operations for
sound-CPU stop/start and mailbox reads.

PASS requires both public mailbox acknowledgement and resident-decoder
telemetry:

```text
mailbox flags         : READY
read sequence         : 1
read index            : 7
last error            : 0

decoder magic         : 0x5244 ("RD")
decoder version       : 1
processed records     : 7
current record        : 7
final timestamp       : 7000 us
decoder ready         : 1
```

A mailbox-only acknowledgement is insufficient.

## Hardware reuse

The generated proof controller calls:

```text
srk_saturn_midi_68k_hardware_adapter_ops()
```

No second SMPC implementation is introduced.

## Explicit exclusions

This source gate does not:

```text
modify accepted R17/R18/R19 integration source
bind a new diagnostics menu action
build a callable candidate
install the decoder in Sound RAM
start the MC68EC000
write SCSP registers
produce a MIDI-driven note
write or inspect the SAROO card
```

## Fail-closed reserved full-build path

The reserved physical-candidate full-build module deliberately raises an error
for every invocation in this tranche.  The next tranche must independently
implement and regression-lock the fresh candidate derivation before that path
is enabled.

## Next gate

After this source gate passes on ERIDU, build the candidate derivation as a
separate tranche:

```text
accepted inert full-build tree
+ exact 239-word decoder
+ exact seven-record proof preload
+ generated installer/runtime/controller seams
+ copied R19 main/menu transformed only inside a fresh output tree
+ release-A / fresh-A interlock
+ no build-time hardware action
+ no SCSP note
+ no SAROO write
```

Only after that candidate full-build succeeds should an independent pre-media
gate and guarded SAROO deployment be designed.
