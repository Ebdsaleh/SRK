# Saturn R23 — independent pre-media and guarded deployment

R23 is the first SRK Saturn candidate that may produce sound because a MIDI
record was processed by the resident MC68EC000 service. That makes the media
boundary materially more important than the earlier silent proofs.

This gate is intentionally separate from the candidate builder.

## Accepted candidate anchors

The completed R23 candidate was built from the accepted inert R23 integration
and produced:

```text
R23 resident image
cb172de4e984dd50fcec195c310cb2945abb10bdaa561d31d52062b7e79038a1

candidate main
cb7a8b1c29957c7bf2fb161f08b8baf4a0fca568dc366b2d90bd6eeb43460790

candidate menu
00dfa1f68e90db05335d7dfb8d53d07b18a36e5e1fc00f3e8380ee0f2e175571

runtime after
993dfdda0c69e8ba1f4cb84669af2e92252f60cfa787d531e8f2a163b54bbaad

proof header
051b46d57d0dafd63399a319cf9f6186e0f6946e5dc6525c1b4457795fef261b

proof source
c037a0306bc39c10ff16408826a5ae438327295285929fd05895827adbdbbace

MODE1 BIN
278099a14985a0ad2e5e3b48a5847cefb5e80afc624974509b10f9c4327d6cb6

CUE
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950

112 sectors / 263424 raw bytes
```

The independent pre-media gate does not merely compare these strings. It
re-opens the candidate project, verifies the complete generated-file inventory,
recomputes the current resident/producer/proof renderers, validates the compiler
object-evidence hashes carried forward from the legacy compiler gate, re-derives
the physical proof program and final state, validates the standalone build
report against the current manifest, and performs a fresh MODE1 verification
through the generic read-only SAROO deployment planner.

## Re-derived physical proof

```text
batch 1 / sequence 1
  32 CONTROL_CHANGE records
  1000..32000 us

batch 2 / sequence 2
  33000 us    NOTE_ON  ch3 note 60 velocity 100
  1033000 us  NOTE_OFF ch3 note 60 velocity 64
```

The independent verifier requires:

```text
0 us       -> zero records / no ACK
15000 us   -> exactly 15 records / no ACK
32000 us   -> sequence 1 ACK / 32 records
refill at old clock -> no premature audio
33000 us   -> Note On due
60 polls   -> audible observation window
1033000 us -> Note Off due / sequence 2 ACK / 34 total
```

It also re-derives:

```text
256 channel-summary words
1024 controller words
128 active-note words
15 voice-state words
final CC74 = 31
final active notes = 0
voice key-on count = 1
voice key-off count = 1
```

## Pre-media behavior

The pre-media command is read-only with respect to the card.

It requires the future destination to be fresh and validates the exact
externally accepted BIN/CUE hashes before it can report:

```text
PRE-MEDIA GATE PASS
SAROO writes : NONE
```

## Whole-card PREPARE

PREPARE re-runs pre-media, then creates a complete off-card SAROO inventory and
immediately verifies it.

The guard manifest must be outside the mounted card. PREPARE performs no card
write and only reports ready when the exact baseline matches.

## Explicit APPLY

APPLY requires both:

1. the exact reviewed SHA-256 of the off-card whole-card guard manifest; and
2. the exact confirmation token:

```text
DEPLOY-R23-MIDI-SCSP-FIRST-NOTE
```

The only permitted additions are:

```text
saroo/ISO/TEST/SRK-Diagnostics-R23
saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.bin
saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.cue
```

No existing path may be overwritten or removed. After the isolated directory is
written, the whole card is revalidated while allowing only those three new
paths to differ. A post-write mismatch triggers a conservative rollback attempt
only when the new destination still contains exactly the two expected files at
their accepted hashes.

## Physical acceptance remains separate

A verified deployment does not mean R23 passed physically.

Real-Saturn acceptance still requires all machine checks to pass **and** the
human observer to hear the MIDI-driven tone during the key-on window and hear it
stop at the scheduled Note Off.

```text
ACK + silence != R23 physical PASS
```

R22A remains immutable and must never be overwritten.
