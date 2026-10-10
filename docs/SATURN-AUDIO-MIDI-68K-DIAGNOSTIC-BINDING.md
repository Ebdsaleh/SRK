# Saturn Audio — Silent MIDI MC68EC000 Diagnostic Binding

## Purpose

This tranche adds the explicit diagnostic control and telemetry surface for the
first real Saturn MC68EC000 protocol acknowledgement proof.

The binding is deliberately compile-time guarded. Normal standalone diagnostic
builds do not define:

```text
SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE
```

and therefore do not include or call the physical-proof controller from
`srk_saturn_main.c`.

A later, fresh off-card R18 candidate gate will enable the guard only inside its
derived build tree after all source tests are accepted.

## Isolation from existing SCSP diagnostics

The proof is **not** attached to the Audio / SCSP screen.

That screen submits the existing deterministic audio request every frame and is
therefore intentionally kept out of the protocol-only acknowledgement path.
Instead, the candidate binding temporarily uses the currently unimplemented:

```text
Timing / Interrupt Test
```

screen slot as an isolated proof surface.

The later R18 candidate gate may relabel that derived menu entry to make the
physical-test image unambiguous. The reusable diagnostic core and ordinary menu
remain unchanged in this source tranche.

## Explicit input safety

Selecting a diagnostics menu entry already uses the Saturn A button. The proof
must never inherit that same A edge and start automatically.

The candidate binding therefore follows this sequence:

```text
enter proof screen with A
-> candidate sees A still held
-> proof action remains DISARMED
-> user releases A
-> proof action becomes ARMED
-> a later fresh A press explicitly starts the proof
```

A held selection button cannot trigger the hardware sequence.

While the proof is RUNNING, additional A presses are ignored.

After a terminal result, a fresh A press performs an explicit controller-state
reset followed by one new begin attempt. This retains the physical-proof
controller's one-shot-until-reset contract while allowing a deliberate rerun.

## Runtime path when the later candidate enables the guard

The explicit A action will call:

```text
srk_saturn_midi_68k_physical_proof_reset()
-> srk_saturn_midi_68k_physical_proof_begin()
```

The already-reviewed controller then owns:

```text
SNDOFF
-> install + exact verify
-> deterministic preload publish + exact verify
-> SNDON
-> RUNNING
```

Each subsequent diagnostics frame performs at most one:

```text
srk_saturn_midi_68k_physical_proof_poll()
```

while the controller remains RUNNING. There is no new busy-wait loop in the
diagnostic binding.

## On-screen telemetry

The candidate proof surface reports:

```text
runtime status
acceptance boundary state
poll count
mailbox flags
read sequence
read index
last error
```

The acceptance boundary is displayed as PASS only when:

```text
runtime status = ACKNOWLEDGED
READ_SEQUENCE  = 1
READ_INDEX     = 1
LAST_ERROR     = 0
```

Failure terminal states are displayed as FAIL; an unstarted or still-running
proof remains NOT RUN or PENDING.

## Source-tranche safety boundary

At this checkpoint:

```text
candidate guard defined      : NO
physical-proof UI compiled   : NO in normal standalone builds
physical-proof controller run: NO
SMPC command executed        : NO
Sound-RAM runtime write      : NO
MC68EC000 execution          : NO
MIDI-driven SCSP note        : NO
SAROO write                  : NO
```

This tranche changes source and tests only. It does not create or deploy R18.

## Next gate

After the source suite is accepted:

1. derive a fresh candidate tree from the accepted inert physical-proof
   full-build baseline;
2. enable `SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE` only in that derived tree;
3. relabel the isolated proof menu entry there;
4. compile and package the complete candidate off-card;
5. verify the build report and exact candidate artifacts;
6. keep SAROO deployment blocked until the previous physical recovery baseline
   is explicitly accepted and the new candidate's pre-media gates are green.

The first real hardware test remains silent protocol acknowledgement only. No
MIDI-driven SCSP note is attempted until that acknowledgement is physically
proven.

> Safer is secure, secure is faster.
