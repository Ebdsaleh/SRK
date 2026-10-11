# Saturn MIDI / MC68EC000 stream scheduler R22A physical acceptance

## Acceptance

R22A is the accepted real-Saturn physical baseline for the resident multi-batch MIDI stream service and timestamp scheduler.

R22 had already physically proven the resident scheduler/refill core and the complete 1408-word state verifier, but its redundant selected-state capture false-failed with `0xE014` because channel-summary word indexes were treated as byte offsets. R22A preserves the accepted resident stream engine and proof program and corrects only those selected-state capture addresses.

The proof remains deliberately silent. It does not generate an SCSP note.

Physical terminal result:

```text
MIDI / 68K STREAM PROOF

Status        : ACKNOWLEDGED
Polls         : 7
Flags         : 0x0001
Read sequence : 2
Read index    : 8
Last error    : 0

Batch count   : 2
Total records : 40

Wait @ 0us    : 1
15ms = 15     : 1
Batch1 ACK    : 1
Refill wait   : 1
Batch2 ACK    : 1
State verify  : 1

CC74          : 31
Program       : 12
Final pitch   : 10036

Stream PASS: refill + timing + state
```

Accepted state:

```text
R22A PHYSICAL ACCEPTANCE      : PASS
REAL SATURN HARDWARE          : PASS
SAROO EXECUTION               : PASS
MC68EC000 STREAM SERVICE      : PASS
TIMESTAMP-GATED EXECUTION     : PASS
BATCH 1 SIZE                  : 32
BATCH 2 SIZE                  : 8
SEQUENCE 1 ACK                : PASS
SAME-QUEUE REFILL             : PASS
NO EARLY BATCH-2 EXECUTION    : PASS
SEQUENCE 2 ACK                : PASS
READ_SEQUENCE                 : 2
READ_INDEX                    : 8
LAST_ERROR                    : 0
TOTAL RECORDS                 : 40
BATCH COUNT                   : 2
STATE_VERIFY                  : 1
SUMMARY WORDS MATCHED         : 256
CONTROLLER WORDS MATCHED      : 1024
ACTIVE-NOTE WORDS MATCHED     : 128
TOTAL STATE WORDS MATCHED     : 1408
PERSISTENT STATE ACROSS REFILL: PASS
SELECTED-STATE CAPTURE        : PASS
MIDI-DRIVEN SCSP NOTE         : NOT ENABLED
```

## R22A correction identity

Correct selected-state Sound-RAM byte addresses:

```text
Program : 0x00001260
Pitch   : 0x00001270
Active  : 0x0000127A
```

R22 had incorrectly used the channel-summary word indexes as byte offsets for pitch and active-note count. On real hardware, the wrong pitch address `0x1268` read the channel pan value `64`, which exactly explained the R22 terminal `Final pitch = 64` false failure.

R22A changes only this instrumentation seam.

Unchanged from the accepted R22 core:

```text
resident MC68EC000 stream image
SH-2 producer
40-record SRKM v1 proof program
32+8 batch split
0 / 15000 / 32000 / 40000 us clock milestones
complete 1408-word state verifier
SCSP output remains disabled
```

## Accepted stream image and compiler identity

```text
Resident stream image SHA-256:
0d64b50b17dcae9318a7c6850ef2d46da84923ccfe0fa9f2611f0287ec59be02

Resident source SHA-256:
69f3ebdca0583310c9bb6508b25bfdbfe77093bc33f67fe70916050b4168ed30

Resident header SHA-256:
d18795d693c9b84ea2504f7a327e47edc55111f76a698fe25164abd95bf1b560

Resident object SHA-256:
aaa824ed0e44a4d40aa49808f77ebeffa4eb2ac9dd6e96f8a3ec22d72df6d8f6

Producer source SHA-256:
ce7e48b49381836828f1f40f9205c530a7aa368c407463049416030d8b5d974d

Producer header SHA-256:
59c12246a82d0b6341746092cc8facfb374fd8da39db003919ca6c976cdb5e61

Producer object SHA-256:
0f782a4751fb3b47c115d5c7bddb8d1a90ef859335aaf288b9d7754dffbb890a
```

## Accepted R22A candidate/media anchors

```text
Candidate manifest:
c8432ea08363afe8c817865ff3daec2b1330a15fda59c700eaac8a8f7891f64d

Candidate build report:
817f3606cbec40e29943dba37cdc8606764d30fa3e7703a268c4bec24f7ee851

Candidate main:
43283c99b18f49255b9d74816e12eb0354aeac1a688b36ac12e74a3069cc4bdc

Candidate menu:
e6220ffc7f0f6ebe1262fff2eac59b044b918eacd652f00324dd878d9af8e3db

Runtime after:
50b20e612fb6ffddd652baa19334373135d21515527f89e7a60acae2a4a7c432

Proof header:
608804011aa3c6c8906bdf89fbcafa6ca35769a8c2f7a7ba849cc47a66502b9f

Proof source:
d840e8f56f15fc82da69c2cf0b406324df66c29abb01fcbb7d9e6e84909e3974

Deployable BIN:
226f91ad37653930a94b6f6a70296488d887613c0aa12031274f689775091f65

Deployable CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

MODE1 media:

```text
112 sectors
263424 raw bytes
```

## Guarded deployment acceptance

R22A PREPARE inventory:

```text
Guard manifest SHA-256:
4b3c969969045a8a1b826d4ab19dc828db529a6523b458c17efd115794dc517c

Card files       : 1610
Card directories : 146
Total file bytes : 60693006547
Files SHA-256ed  : 186
Exact pre-write  : MATCH
```

R22A APPLY:

```text
Pre-write whole-card : MATCH
Post-write whole-card: PASS (only authorised R22A additions differ)
Result               : R22A DEPLOYMENT VERIFIED
```

Only these fresh paths were added:

```text
saroo/ISO/TEST/SRK-Diagnostics-R22A
saroo/ISO/TEST/SRK-Diagnostics-R22A/SRK-Diagnostics.bin
saroo/ISO/TEST/SRK-Diagnostics-R22A/SRK-Diagnostics.cue
```

Existing SAROO content was not overwritten or removed.

## Physical evidence

The user supplied the real-Saturn recording of the corrected R22A run:

```text
Filename : SRK-DIAG(20261011-122623).mp4
Bytes    : 6382393
Duration : 30.700000 seconds
SHA-256  : 4aa31c761e6b20bc25736c0342d4e71387ed551e7be3901bfc245224180d3dfa
```

The video itself is intentionally not committed to the source repository.

## What this proves

R22A physically closes the multi-batch/refill and producer-clock scheduling milestone:

```text
SH-2 publishes batch 1 with sequence 1
-> producer clock remains 0 us
-> MC68EC000 executes zero records early
-> producer clock advances to 15000 us
-> exactly 15 records are applied, with no batch ACK
-> clock advances to 32000 us
-> all 32 first-batch records are applied
-> sequence 1 is acknowledged
-> SH-2 refills the same 32-record queue with sequence 2
-> producer clock remains at the old 32000-us value
-> zero second-batch records execute prematurely
-> clock advances to 40000 us
-> all eight second-batch records are applied
-> sequence 2 is acknowledged
-> resident MIDI state survives the refill
-> complete 1408-word state matches the host reference model
-> corrected selected-state capture matches the same accepted state
-> terminal Stream PASS is returned
```

The real Saturn therefore has a physically accepted resident MIDI command engine that can consume more data than fits in one queue, preserve state across refills, and gate execution against producer-published timestamps.

## Still excluded

R22A does not yet prove:

```text
final hardware-derived MIDI timebase
voice allocation
SCSP slot-state allocation
MIDI-driven SCSP key-on/key-off
MIDI-generated audio
polyphony
voice stealing
```

R17, R18, R19, R20, R21, R22 evidence and R22A are immutable historical hardware anchors. R22 remains preserved as the physical false-negative instrumentation case; R22A is the clean accepted stream/scheduler baseline.

The next milestone is the first sound-producing MIDI tranche:

```text
voice allocator
+ SCSP slot-state model
+ first MIDI-driven SCSP note
```
