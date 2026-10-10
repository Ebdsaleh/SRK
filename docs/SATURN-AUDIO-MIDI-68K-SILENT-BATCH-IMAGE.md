# Saturn Audio — Silent Full-Batch MIDI/MC68EC000 Image Gate

## Purpose

R18 physically proved that SRK-owned code can be installed into Saturn Sound RAM,
executed by the real MC68EC000, acknowledge one reviewed queue record, and return
that acknowledgement to the SH-2.

The next step remains silent.  This gate expands the resident program from one
record to the complete deterministic 27-record SRKM diagnostic batch without
introducing SCSP voice writes.

The first full-batch image is intentionally **exact-batch and unrolled**.  It is
not yet the general-purpose resident MIDI decoder.  This keeps the next physical
boundary focused on one question:

```text
Can the real MC68EC000 validate the complete known queue and publish the exact
reviewed silent channel/controller/note state before acknowledging all records?
```

A later tranche may replace the exact validator with a general looping decoder
after this boundary is accepted on real hardware.

## Accepted prerequisite

R18 physical acceptance remains:

```text
MIDI / MC68EC000 PROOF : PASS
MAILBOX STATUS         : ACKNOWLEDGED
READ_SEQUENCE          : 1
READ_INDEX             : 1
LAST_ERROR             : 0
MIDI-DRIVEN SCSP NOTE  : NOT ENABLED
```

R18 remains immutable as the accepted one-record recovery/validation image.

## Program window

The silent full-batch program is separate from R18's small proof image:

```text
program start : 0x00004000
program words : 5066
program bytes : 10132
program end   : 0x00006794
reviewed max  : 0x00008000
stack         : 0x0007FFF0
```

The program window is above the deterministic MIDI tone bank and does not alter
the mailbox/state regions below `0x2000`.

## Instruction subset

The generator uses only the already-reviewed simple MC68000 forms plus
word-sized branches:

```text
MOVE.W (abs.W),Dn
MOVE.W #imm,(abs.W)
MOVE.W Dn,(abs.W)
CMPI.W #imm,Dn
ANDI.W #imm,Dn
Bcc.W
BRA.W
BRA.S -2 terminal hold
```

The word-branch displacement follows the M68000 rule that branch PC is the
branch instruction address plus two.

No indexed addressing, address-register loop, subroutine, interrupt, SCSP or
SMPC instruction path is introduced in this image.

## Runtime contract

The resident image:

```text
1. waits for READY;
2. validates mailbox magic/version/capacity;
3. requires QUEUE_COUNT = 27 and WRITE_INDEX = 27;
4. validates all 108 queue words (27 records x 4 words);
5. publishes the exact model-derived silent state;
6. writes silent telemetry;
7. sets READ_INDEX = 27;
8. copies WRITE_SEQUENCE to READ_SEQUENCE;
9. sets LAST_ERROR = 0;
10. enters a terminal hold.
```

Public `READ_INDEX` remains zero throughout validation and state publication.
Partial progress therefore never masquerades as a completed batch acknowledgement.

## Failure contract

New full-batch-specific errors are:

```text
1  mailbox magic
2  mailbox version
3  mailbox contract/capacity
4  empty queue
6  wrong exact batch count/index
7  canonical queue record mismatch
```

A record mismatch leaves the public read sequence/index unacknowledged and leaves
silent-state-ready at zero.  Telemetry retains the zero-based record index being
validated when the mismatch occurred.

## Silent state publication

On success the image publishes the existing reviewed command-engine state:

```text
0x1200-0x13FF  16 channel summaries
0x1400-0x1BFF  128 controller bytes x 16 channels
0x1C00-0x1CFF  128-note logical-key bitmap x 16 channels
0x1D00-0x1DFF  telemetry
```

All runtime writes made by this program remain below `0x2000`.

The image does not access SCSP registers and does not generate audio.

## Independent machine-word regression model

The regression test does not merely compare Python data structures.  It contains
a tiny interpreter for exactly the emitted MC68000 subset and executes the actual
generated 5066-word image against synthetic Sound RAM.

The regression gate requires:

```text
canonical batch
  -> READ_INDEX = 27
  -> READ_SEQUENCE = WRITE_SEQUENCE
  -> LAST_ERROR = 0
  -> state-ready = 1
  -> exact model-derived summaries/controllers/note bitmap

corrupt queue record
  -> READ_INDEX remains 0
  -> READ_SEQUENCE remains 0
  -> LAST_ERROR = 7
  -> state-ready remains 0
  -> telemetry identifies failing record

wrong queue count/index
  -> no acknowledgement
  -> LAST_ERROR = 6

all runtime writes
  -> address < 0x2000
```

## Off-card compiler gate

The compiler probe renders the generated C representation only inside a fresh
off-card output directory and compiles it with the same SH-ELF C flags used by
the accepted standalone pipeline:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The probe records:

```text
image SHA-256
image geometry
generated header/source SHA-256
object SHA-256
compiler argv/return code
```

Policy remains:

```text
linker invoked              NO
ISO builder invoked         NO
SAROO writes                NO
Sound RAM writes            NO
SCSP MMIO                   NO
SMPC commands               NO
MC68EC000 program installed NO
MC68EC000 execution         NO
```

## Real compiler command

After the repository source tests pass, use a **fresh off-card output path**:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_silent_batch_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\SRK-Workspace\MIDI-68K-SILENT-BATCH-COMPILE-GATE1"
```

Expected final boundary:

```text
Result : SUCCESS
```

The complete output, especially the image/source/header/object SHA-256 values,
should be preserved before a full standalone build gate is designed.

## What this gate does not authorize

A green source/compiler gate does **not** authorize:

```text
R18 modification
SAROO deployment
Sound-RAM installation on hardware
MC68EC000 execution on hardware
SCSP MIDI note generation
```

The next stage after compiler acceptance is a full standalone build-integration
gate for a new silent candidate.

> Safer is secure, secure is faster.
