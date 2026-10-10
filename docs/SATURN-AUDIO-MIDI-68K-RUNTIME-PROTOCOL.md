# Saturn Audio MIDI — Silent MC68EC000 runtime protocol contract

This tranche defines the first bounded runtime orchestration contract for SRK's
Saturn MIDI proof. It still does not connect that contract to a production menu
control or to direct Saturn MMIO.

The purpose is to freeze sequencing and telemetry before the separately reviewed
hardware adapter is allowed to issue the already-accepted SMPC sound-CPU
commands.

## Status

The orchestration layer is present as C89-compatible source but is **not called
by any existing standalone diagnostic source**.

No R18 deployment is authorized by this tranche.

## Accepted prerequisites

The following pieces were already source-, compiler-, and full-build-gated
before this contract was added:

- deterministic SRKM MIDI event/tone data;
- SH-2 mailbox preload producer;
- protocol-only MC68EC000 program image;
- bounded MC68EC000 Sound-RAM installer and exact read-back verifier.

The installer still requires the MC68EC000 to be stopped before it is called.

## Deliberate adapter boundary

`srk_saturn_midi_68k_runtime.c` does not contain direct Saturn register or Sound
RAM addresses. Instead it consumes an operation table:

```text
stop_sound_cpu
install_program
publish_preload
verify_preload
start_sound_cpu
read_mailbox_word
```

This separates two things that must be reviewed independently:

1. **protocol order and state classification**;
2. **hardware-specific SMPC/Sound-RAM access**.

A later tranche will provide the Saturn adapter only after this orchestration
source has passed its own source and legacy-compiler gates.

## Locked operation order

`srk_saturn_midi_68k_protocol_begin()` performs exactly:

```text
validate operation table
-> stop sound CPU
-> install + verify protocol-only 68K program
-> publish deterministic preload
-> verify deterministic preload
-> start sound CPU
-> return RUNNING
```

Failure returns immediately at the failed stage. In particular, if install or
preload verification fails, the orchestrator does not request a sound-CPU
restart.

## Runtime statuses

```text
0 NOT_STARTED
1 SOUND_STOP_FAILED
2 INSTALL_FAILED
3 PRELOAD_FAILED
4 SOUND_START_FAILED
5 RUNNING
6 ACKNOWLEDGED
7 CONSUMER_ERROR
```

## Non-blocking protocol telemetry

The poll API reports only the four mailbox words needed for the first silent
proof:

```text
flags
read_sequence
read_index
last_error
```

The first protocol consumer is accepted only when:

```text
READY flag      set
READ_SEQUENCE   1
READ_INDEX      1
LAST_ERROR      0
```

A non-zero `LAST_ERROR` is classified as `CONSUMER_ERROR`. Otherwise an
incomplete acknowledgement remains `RUNNING`; the poll routine does not spin or
wait.

## Hardware adapter anchors reserved for review

The Python contract locks the same already-accepted Saturn anchors used by the
existing physical audio diagnostic:

```text
SMPC COMREG   0x2010001F
SMPC SF       0x20100063
VDP2 TVSTAT   0x25F80004
Sound RAM     0x25A00000
SNDON         0x06
SNDOFF        0x07
SMPC timeout  1000000 iterations
```

These constants are intentionally **not wired into the C orchestration layer in
this tranche**. The forthcoming hardware adapter must reproduce the accepted
Type-B command flow and safe command-window behavior from the existing Saturn
audio implementation rather than inventing a new sequence.

## Safety boundary

This tranche itself performs no runtime hardware operation because no production
code constructs an operation table or calls the begin/poll functions.

It therefore adds no:

- direct SMPC register access;
- Sound RAM access;
- SCSP access;
- reset-vector change;
- MC68EC000 launch;
- SAROO/card write;
- menu-control binding.

## Next gates

After the source suite passes:

1. compile the adapter-neutral runtime source with the real legacy SH-ELF GCC
   and normal standalone C flags;
2. link it, still uncalled, into a fresh complete off-card standalone image;
3. implement the Saturn hardware adapter using the already-accepted SMPC flow;
4. compile/link that adapter off-card while still unbound to a menu control;
5. only then prepare a guarded R18 silent protocol candidate.

The first physical proof remains intentionally silent. Audible MIDI-driven SCSP
output begins only after the MC68EC000 mailbox acknowledgement is physically
proven.

> Safer is secure, secure is faster.
