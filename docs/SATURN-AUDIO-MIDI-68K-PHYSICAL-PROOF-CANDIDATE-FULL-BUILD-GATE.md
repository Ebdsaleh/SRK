# Saturn Audio — Silent MIDI MC68EC000 Physical-Proof Candidate Full-Build Gate

## Purpose

This gate creates SRK's first standalone Saturn image in which the already
reviewed silent MIDI/MC68EC000 physical-proof controller is both linked **and
explicitly callable from the diagnostic UI**.

It is still an **off-card build gate**. Preparing and building the candidate
does not access a Saturn, issue SMPC commands, write Sound RAM, execute the
MC68EC000, or write a SAROO card.

The first real hardware action remains a later, separately guarded deployment
and an explicit user-triggered proof.

## Accepted baseline

The input is not an arbitrary standalone project. It must be a previously
successful **inert physical-proof full-build tree** whose manifest and build
report agree and whose recorded state proves:

```text
physical proof linked       true
physical proof called       false
hardware adapter linked     true
hardware adapter called     false
runtime called              false
installer called            false
68K program installed       false
reset vectors changed       false
mailbox producer called     false
SMPC commands executed      false
Sound-RAM runtime writes    false
MC68EC000 execution         false
behaviorally active         false
```

Every generated input named by that manifest is re-hashed before derivation.
The accepted baseline is never modified.

## Fresh-tree derivation

The candidate gate copies only manifest-pinned generated inputs into a fresh
off-card directory.

It then replaces two files in that fresh tree from the reviewed repository
sources:

```text
src/srk_saturn_main.c
src/srk_diag_menu.c
```

The candidate copy of `srk_saturn_main.c` receives:

```c
#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1
```

The repository source remains disabled by default.

The isolated placeholder menu label is changed only in the derived candidate:

```text
Timing / Interrupt Test
```

becomes:

```text
MIDI 68K Silent Proof
```

The normal Audio / SCSP diagnostic screen is not reused for this proof.

## Explicit physical action contract

When a later deployed candidate enters the proof screen:

```text
select screen with A
-> selection A is still held
-> proof remains disarmed
-> release A
-> proof action becomes armed
-> press A again
-> explicit reset + bounded begin
```

While the proof is `RUNNING`, further A presses do not restart it.

Polling is non-blocking and occurs at most once per diagnostics frame while the
proof remains `RUNNING`.

## Success boundary

The proof screen reports:

```text
runtime status
boundary result
poll count
flags
read sequence
read index
last error
```

Physical success remains exactly:

```text
runtime status = ACKNOWLEDGED
READ_SEQUENCE  = 1
READ_INDEX     = 1
LAST_ERROR     = 0
```

This proves the silent round trip:

```text
SH-2
-> Sound RAM preload/mailbox
-> installed MC68EC000 program
-> MC68EC000 execution
-> mailbox acknowledgement
-> SH-2 observation
```

## Still no MIDI-driven SCSP note

This candidate does **not** add MC68EC000-driven note output.

The proof remains protocol-only. Existing standalone SCSP diagnostics remain a
separate, already-proven path.

No MIDI-driven SCSP note is attempted until the silent physical acknowledgement
boundary has passed on real Saturn hardware.

## Build-time safety boundary

The candidate manifest records that the image contains a behaviorally active
path **if later deployed and explicitly triggered**, while the build itself
performs none of those actions:

```text
proof UI compiled                    true
proof call path compiled             true
proof called during build            false
user trigger required                true
trigger button                       A
release-after-screen-entry required  true
MIDI-driven SCSP note attempted      false
build-time SMPC commands             false
build-time Sound-RAM writes          false
build-time MC68EC000 execution       false
SAROO write                          false
off-card only                        true
```

The normal Python-native standalone builder then performs the existing:

```text
legacy SH-ELF C compilation
startup assembly
mixed-format SBL link
ISO creation
packaged-PCM verification
MODE1/2352 BIN/CUE packaging
```

## CLI

```text
python -m rikai_kotoba.tools.saturn_midi_68k_physical_proof_candidate_full_build_gate \
  --baseline-project <accepted-inert-physical-proof-tree> \
  --output <fresh-off-card-candidate-tree>
```

There is deliberately no:

```text
--card-root
--apply
--confirm
```

and the candidate gate imports no SAROO deployment module.

A successful candidate build is therefore **not** deployment authorization.

## Gate order after SUCCESS

After the source tests and this complete off-card build pass:

1. inspect the derived manifest and full build report;
2. verify the compiled candidate/tree provenance and expected BIN/CUE;
3. run an independent pre-media/deployment-plan gate;
4. only then authorize one guarded R18 SAROO deployment using the already
   accepted R17 physical recovery baseline;
5. on real hardware, enter `MIDI 68K Silent Proof`;
6. release A after entering the screen;
7. press A once to start the silent proof;
8. accept only `ACKNOWLEDGED`, sequence `1`, index `1`, error `0`.

No MIDI-driven SCSP note belongs to this physical checkpoint.

> Safer is secure, secure is faster.
