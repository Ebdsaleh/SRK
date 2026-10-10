# Saturn Audio MIDI MC68EC000 Protocol Consumer

This tranche defines the first SRK-owned MC68EC000 program image for the MIDI
path.  It is deliberately **protocol-only** and **not launched** by the Saturn
diagnostic yet.

The goal is to prove SH-2 -> Sound RAM -> MC68EC000 mailbox semantics before any
SCSP slot manipulation is added.

## Scope

The program does only this:

1. poll the mailbox READY flag;
2. validate mailbox magic/version;
3. validate the bounded queue-capacity contract;
4. require a non-empty queue;
5. read and validate all four words of the canonical first SRKM event;
6. acknowledge exactly one consumed record;
7. copy the producer write-sequence to the read-sequence;
8. publish a bounded error code if validation fails;
9. enter a deterministic hold loop.

It does **not**:

- configure an SCSP slot;
- key a slot on or off;
- issue SNDON/SNDOFF;
- write an SCSP register;
- touch CD hardware;
- access SAROO;
- produce audible output.

No current production runtime installs or launches this program.

## Sound-RAM placement

The proof program is assigned:

```text
start       0x00000600
end         0x000006A2 (exclusive)
size        162 bytes / 81 words
stack       0x0007FFF0
```

This remains below the MIDI mailbox at `0x00001000` and above the accepted
vector/dummy-loop ownership ending at `0x00000402`.

The program SHA-256 over its big-endian word stream is:

```text
2a0f30068be2815953569e2717af6c92197b08897fdca744607f5b4bee14e5c2
```

## Canonical first record

The producer's first queued SRKM record is already locked as:

```text
word 0  time_us high   0x0000
word 1  time_us low    0x0000
word 2  opcode/channel 0x0400   CONTROL_CHANGE, channel 0
word 3  data0/data1    0x0000   controller 0, value 0
```

The protocol-only program reads and validates all four words before publishing
an acknowledgement.  This is intentionally tied to the deterministic SRK test
sequence.  A later general-purpose consumer will decode arbitrary queue records
rather than require this exact first record.

## Mailbox acknowledgement

On success:

```text
READ_INDEX     = 1
READ_SEQUENCE  = WRITE_SEQUENCE
LAST_ERROR     = 0
```

The program then remains in a local `BRA.S` hold loop.  READY remains owned by
the SH-2 producer; this proof does not invent a second ownership rule.

## Error values

```text
1  mailbox magic mismatch
2  mailbox version mismatch
3  queue-capacity contract mismatch
4  queue empty after READY
5  canonical first-record mismatch
```

On error the program writes `LAST_ERROR` once, then enters its error hold loop.

## Encoding policy

The image generator uses a deliberately small reviewed 68000 subset:

```text
MOVE.W (xxx).W,Dn
CMPI.W #imm,Dn
ANDI.W #imm,Dn
MOVE.W #imm,(xxx).W
MOVE.W Dn,(xxx).W
BEQ.S
BNE.S
BRA.S
```

All mailbox and queue addresses used by this proof are positive 16-bit
addresses, so absolute-short addressing stays within the intended Sound-RAM
range.  Short branch displacements are generated and range-checked by Python.

This source-generated image is preferable to introducing another assembler or
build-system dependency merely for the 162-byte proof program.

## Generated C bridge

The repository now contains:

```text
integrations/saturn/standalone/srk_saturn_midi_68k_program.h
integrations/saturn/standalone/srk_saturn_midi_68k_program.c
```

These files contain only constant program words and metadata.  They contain no
hardware pointer, `volatile` declaration, SCSP address, SMPC command, or launch
function.

The committed C/H files must remain byte-for-text identical to the Python
renderer.

## Next gate

After the source tests pass:

1. compile the generated constant C image with the legacy SH-ELF compiler;
2. link it into another fresh full off-card standalone image;
3. keep the MC68EC000 program uninstalled/unlaunched;
4. only after that succeeds, define a bounded installer that replaces the dummy
   reset PC with `0x00000600` in a fresh hardware candidate;
5. first hardware proof remains protocol-only — still no audible SCSP action.

External MIDI I/O remains out of scope.

> Safer is secure, secure is faster.
