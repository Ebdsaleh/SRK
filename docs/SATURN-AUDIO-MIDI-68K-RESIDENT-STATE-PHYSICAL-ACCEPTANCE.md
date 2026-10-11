# Saturn MIDI / MC68EC000 resident state physical acceptance

## Acceptance

R21 is the accepted first real-Saturn proof that the resident MC68EC000 applies SRKM v1 commands into the complete reviewed MIDI state model, not merely that it consumes queue records.

The proof remains deliberately silent. It does not generate an SCSP note.

Physical terminal result:

```text
MIDI / 68K STATE PROOF
20 records - full MIDI state verification

Status        : ACKNOWLEDGED
Boundary      : PASS
Polls         : 1
Flags         : 0x0001
Read sequence : 1
Read index    : 20
Last error    : 0
State verify  : 1

CH3 program   : 12
CH3 bank MSB  : 5
CH3 bank LSB  : 9
CH3 volume    : 91
CH3 pan       : 73
CH3 expression: 101
CH3 sustain   : 1
CH3 pitch     : 10036
CH3 active    : 1
CH3 CC74      : 66
CH9 program   : 33
CH9 active    : 1

State PASS: full MIDI state matched
```

Accepted state:

```text
R21 PHYSICAL ACCEPTANCE : PASS
REAL SATURN HARDWARE    : PASS
SAROO EXECUTION         : PASS
MC68EC000 STATE ENGINE  : PASS
ALL SRKM V1 OPCODES     : PASS
MAILBOX STATUS          : ACKNOWLEDGED
READ_SEQUENCE           : 1
READ_INDEX              : 20
LAST_ERROR              : 0
STATE_VERIFY            : 1
SUMMARY WORDS MATCHED   : 256
CONTROLLER WORDS MATCHED: 1024
ACTIVE-NOTE WORDS MATCHED: 128
TOTAL STATE WORDS MATCHED: 1408
MIDI-DRIVEN SCSP NOTE    : NOT ENABLED
```

## Accepted state image identity

```text
Program address : 0x00004000
Stack           : 0x0007FFF0
Word count      : 4898
Byte count      : 9796
Program end     : 0x00006644
Runtime records : 1..32

SHA-256:
39d5c1116affa95e2be7d5f94342e0ba70bfebf845b6f2cce292946894bd5bb9
```

The R21 proof uses a 20-record program spanning all seven SRKM v1 opcode classes across channels 3 and 9. The verifier compares the complete post-execution state against the existing host-side command-engine model before PASS can be returned.

## Accepted candidate/media anchors

```text
Candidate manifest:
13fbad00e476a0058b6941d04991063b69f0b5ec50a0b059d6c5dbe526bb1ea9

Candidate build report:
4d7835de938c04a8cbb4b138413568404c498e2f0165b4be7f7eaae146cd046c

Candidate main:
0da7f204c458844c4d3cef58aad6da94f6c1e6c5de1fb5a2fcce9ff28ce6d5a5

Candidate menu:
065421f7f09064d560bfaddf6daca107d5faba054a95b259e38aa013e0771d1d

Runtime after:
177c22dacbfe01cef61557a8d2d2b65d609fa5f574df8d6472203f9663feacee

Deployable BIN:
56265bc7a535f4cb5b2ab89ba8ff5cebcbf3a0aee0b6d435436a7e7fffd116b6

Deployable CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

R21 guarded deployment was verified against the exact whole-card PREPARE baseline:

```text
Guard manifest SHA-256:
28bf32722bcf194cf576718b64f37beb048c453356aadfe0441fcf42276aea63

Pre-write whole-card : MATCH
Post-write whole-card: PASS (only authorised R21 additions differ)
```

Only the fresh `SRK-Diagnostics-R21` directory and its exact BIN/CUE were added.

## Physical evidence

The user supplied the first-run real-Saturn recording before any retry/reset:

```text
Filename : SRK-DIAG(10).mp4
Bytes    : 6381063
Duration : 30.633333 seconds
SHA-256  : bf423e8d65bae151b869849724fab8c86aa9eaa770e4de68842b361bf901eff8
```

The video itself is intentionally not committed to the source repository.

## What this proves

R21 physically closes the Phase-B state-mutation risk:

```text
SH-2 publishes the reviewed 20-record runtime queue
-> accepted R20 hardware stop/start path
-> exact compiler-accepted Phase-B state image is installed
-> real MC68EC000 executes the dynamic state decoder
-> all seven SRKM v1 opcode classes mutate resident MIDI state
-> channel summaries are maintained
-> full 16x128 controller matrix is maintained
-> full 16x128 active-note bitmap is maintained
-> mailbox/RS telemetry reaches completion
-> SH-2 verifies every reviewed state word against the host model
-> PASS is returned only after all 1408 words match
```

The physical result therefore proves useful persistent MIDI command state on the real sound CPU.

## Still excluded

R21 does not yet prove:

```text
multi-batch/refill streaming
timestamp-gated execution across batches
continuous playback service
voice allocation
SCSP slot programming
MIDI-generated audio
polyphony
```

R17, R18, R19, R20 and R21 are immutable historical hardware anchors.

The next implementation milestone combines multi-batch/refill service and timestamp scheduling as one larger capability tranche while preserving R21 unchanged.
