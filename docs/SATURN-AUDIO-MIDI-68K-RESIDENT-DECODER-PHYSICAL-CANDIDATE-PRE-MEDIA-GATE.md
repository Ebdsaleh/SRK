# Saturn MIDI/68K Resident Decoder — R20 Physical Candidate Pre-Media Gate

## Purpose

This gate independently re-opens the completed R20 seven-record resident-decoder physical candidate before any SAROO write is allowed.

It is intentionally read-only. It has no apply operation, no confirmation token and no file-copy path.

## Candidate under review

The candidate is expected to have been built by the resident-decoder physical-candidate full-build gate and to retain the exact general decoder image accepted by the earlier compiler/inert gates.

Accepted decoder geometry:

```text
program address : 0x00004000
word count      : 239
byte size       : 478
program end     : 0x000041DE
runtime records : 1..32
embedded records: none
```

## Independent provenance checks

The gate re-opens the candidate directory from disk and verifies:

```text
standalone manifest schema/mode
standalone build report success
report -> current manifest SHA binding
every manifest-pinned generated input
inherited inert resident-decoder gate
externally accepted decoder image SHA-256
externally accepted compiler source SHA-256
externally accepted compiler header SHA-256
externally accepted compiler object SHA-256 evidence
candidate main/menu/runtime hashes
all eight generated installer/preload/runtime/proof seam hashes
```

The current resident-decoder generator must still reproduce the accepted 239-word image and exact geometry.

## Seven-record proof independence

The gate reconstructs the reviewed proof program from the current generator and requires:

```text
records          : 7
final timestamp  : 7000 us
channels         : 0..6
opcode coverage  : all seven SRKM v1 opcodes exactly once
```

The candidate preload source/header must byte-match the reviewed renderers. The same is required for the installer, runtime and physical-proof source/header pairs.

## Required physical-candidate contract

The candidate manifest must still record:

```text
candidate define       : SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE
menu label             : MIDI 68K Decoder Proof
trigger                : A
screen-entry interlock : release A, then fresh A press
polling                : at most once per frame while RUNNING
expected sequence      : 1
expected index         : 7
expected last error    : 0
proof records          : 7
proof final time       : 7000 us
all opcodes once       : yes
```

The build-time policy must remain:

```text
decoder linked                    : yes
decoder installed during build    : no
decoder executed during build     : no
decoder candidate bound           : yes
MIDI-driven SCSP note attempted   : no
build-time SMPC commands          : no
build-time Sound-RAM writes       : no
build-time MC68EC000 execution    : no
SAROO write                       : no
off-card only                     : yes
```

## Runtime PASS contract

The reviewed R20 candidate is not allowed to report `ACKNOWLEDGED` from the mailbox alone.

Mailbox requirements:

```text
READY          : set
READ_SEQUENCE  : 1
READ_INDEX     : 7
LAST_ERROR     : 0
```

Decoder telemetry requirements:

```text
magic          : 0x5244 ("RD")
version        : 1
processed      : 7
current_record : 7
final time     : 7000 us
ready          : 1
```

The physical UI must retain the release-A/fresh-A trigger path and expose the decoder proof rather than the older R19 batch proof.

## Media verification

After provenance checks, the gate invokes only the existing read-only standalone-image deployment planner.

That planner verifies:

```text
fresh SAROO destination
CUE references the expected BIN
MODE1/2352 track structure
raw sector count/size consistency
source BIN/CUE hashes
```

The candidate BIN and CUE must exactly match externally supplied hashes captured from the successful R20 full-build output.

## Read-only rule

This gate performs no SAROO write.

It must end with:

```text
Fresh MODE1 verification: PASS
Candidate provenance    : PASS
Decoder provenance      : PASS
Seven-record proof      : PASS
Externally accepted hash: PASS
SAROO destination       : FRESH
SAROO writes            : NONE

Result                  : PRE-MEDIA GATE PASS
```

A passing pre-media gate authorizes only the design of the next two-phase whole-card guard. It does not authorize deployment by itself.

## Next gate

After a real-card PRE-MEDIA PASS, build an R20-specific guarded deployment using the already accepted R19 whole-card philosophy:

```text
PREPARE
-> rerun R20 pre-media gate
-> create whole-card inventory off-card
-> exact immediate verification
-> zero card writes

APPLY
-> exact PREPARE manifest SHA
-> R20-specific confirmation token
-> rerun pre-media gate
-> exact pre-write whole-card match
-> create only fresh R20 destination/BIN/CUE
-> exact post-write allow-list verification
```

Only after guarded deployment should the R20 seven-record proof execute on the real Saturn.
