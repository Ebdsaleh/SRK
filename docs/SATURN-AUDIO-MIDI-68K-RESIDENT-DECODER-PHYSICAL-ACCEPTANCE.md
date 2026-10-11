# Saturn MIDI / MC68EC000 resident decoder physical acceptance

## Acceptance

R20 is the accepted first real-Saturn proof of the general runtime-sized SRKM v1 resident decoder loop.

The proof is deliberately silent. It does not generate an SCSP note.

Physical terminal result:

```text
MIDI / 68K DECODER PROOF
7 records - no MIDI SCSP note

Status        : ACKNOWLEDGED
Boundary      : PASS
Polls         : 1
Flags         : 0x0001
Read sequence : 1
Read index    : 7
Last error    : 0
Processed     : 7
Current       : 7
Decoder ready : 1

Success: sequence=1 index=7 error=0
```

Accepted state:

```text
R20 PHYSICAL ACCEPTANCE : PASS
REAL SATURN HARDWARE    : PASS
SAROO EXECUTION         : PASS
GENERAL RUNTIME LOOP    : PASS
ALL SRKM V1 OPCODES     : PASS
MC68EC000 EXECUTION     : PASS
MAILBOX STATUS          : ACKNOWLEDGED
READ_SEQUENCE           : 1
READ_INDEX              : 7
LAST_ERROR              : 0
PROCESSED                : 7
CURRENT                  : 7
DECODER_READY            : 1
MIDI-DRIVEN SCSP NOTE    : NOT ENABLED
```

## Accepted decoder identity

```text
Program address : 0x00004000
Stack           : 0x0007FFF0
Word count      : 239
Byte count      : 478
Program end     : 0x000041DE
Runtime records : 1..32
Embedded records: NONE

SHA-256:
d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4
```

The seven-record physical proof is intentionally not the accepted R19 27-record payload. It contains each SRKM v1 opcode exactly once and reaches a final timestamp of 7000 us.

## Accepted candidate/media anchors

```text
Candidate manifest:
2592a50788cf2edac7e9fd5a62a7b2b52b24c3d0e1add8939a98b7c3440a310c

Candidate build report:
044b2dd7eb9490c4e6f0aff43a73ab6d2c36b387926173020a4d95fdab57d4ae

Deployable BIN:
8dfe27be4e33db1f2610b3a9facfa1270a508ec112de08009e362e1e24cc9d5a

Deployable CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

R20 guarded deployment was verified against the whole-card PREPARE baseline. Only the fresh R20 directory and its exact BIN/CUE were added.

## Physical evidence

The user supplied the first-run real-Saturn recording before any retry/reset:

```text
Filename : SRK-DIAG(9).mp4
Bytes    : 9624177
Duration : 46.233333 seconds
SHA-256  : 515df782f521226c3b090bfc33e873f12f485b37aa335c8563cd47fed51d6da7
```

The video itself is intentionally not committed to the source repository.

## What this proves

R20 physically closes the architectural risk that R19 deliberately left open:

```text
SH-2 runtime-sized queue publication
-> accepted R19 SMPC stop/start adapter
-> exact 239-word content-independent decoder installation
-> real MC68EC000 execution
-> A0 pointer-driven queue traversal
-> runtime loop/count handling
-> validation of all seven SRKM v1 opcode classes
-> dynamic processed/current telemetry
-> mailbox acknowledgement of the actual runtime count
```

R20 is therefore distinct from R19's fixed/unrolled 27-record consumer even though both expose a deliberately similar silent proof UI.

## Still excluded

R20 does not yet prove:

```text
dynamic channel/controller/note-state mutation
multi-batch/refill streaming
timestamp scheduling
voice allocation
SCSP slot programming
MIDI-generated audio
polyphony
```

R17, R18, R19 and R20 are immutable historical hardware anchors.

The next implementation milestone is Phase B: dynamic MIDI channel/controller/note-state mutation by a new resident decoder image, while preserving R20 unchanged.
