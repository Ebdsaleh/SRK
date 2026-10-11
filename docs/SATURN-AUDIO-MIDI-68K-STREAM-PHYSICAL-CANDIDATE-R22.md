# Saturn MIDI 68K stream/scheduler physical candidate — R22

R22 is the first real-Saturn candidate for the continuous resident MIDI stream
service.  It derives from the accepted R21 full-state physical baseline through
the compiler-accepted inert stream/scheduler integration.

## Scope

R22 remains silent.  It does not allocate SCSP voices or generate MIDI-driven
audio.  Its job is to prove the transport/scheduling service on the real
MC68EC000 before audio is enabled.

The physical program contains 40 SRKM v1 records split across the reviewed
32-record queue boundary:

```text
batch 1: records  1..32, sequence 1, timestamps  1000..32000 us
batch 2: records 33..40, sequence 2, timestamps 33000..40000 us
```

The proof automatically publishes a controlled microsecond clock and requires
these milestones in order:

```text
clock =     0 us -> 0 records executed, no ACK
clock = 15000 us -> exactly 15 records executed, no ACK
clock = 32000 us -> batch 1 complete, sequence 1 ACK
refill sequence 2 while clock remains 32000 us
                  -> 0 records from batch 2 execute early
clock = 40000 us -> batch 2 complete, sequence 2 ACK, 40 total
```

The first batch writes controller 74 repeatedly and leaves `CC74 = 31`.  The
second batch never touches controller 74, but applies program, note, pitch bend,
volume, channel pressure, poly-aftertouch, note-off and another note-on event.
The final expected selected state is:

```text
CC74              : 31
program           : 12
pitch bend        : 10036
active-note count : 1
last note         : 67
last velocity     : 88
```

That selected state is only the visible summary.  PASS also requires complete
word-for-word state equality against the host model across:

```text
256 channel-summary words
1024 controller words
128 active-note words
```

## Physical state machine

After a fresh A press the SH-2 proof:

1. Stops the sound CPU through the hardware adapter already physically accepted
   by R21.
2. Clears only the reviewed mailbox/service control ranges while the sound CPU
   is stopped.
3. Installs and verifies the exact compiler-accepted resident stream image.
4. Starts the sound CPU.
5. Waits for stream service magic/version and `WAIT_BATCH`.
6. Drives the clock/refill milestones above.
7. Verifies the complete final MIDI state.
8. Returns `ACKNOWLEDGED` only after every timing/refill/state check passes.

The public screen exposes the phase, service flags, current index, batch count,
total records, each milestone PASS bit, full-state verification status and
selected persistent/final state values.

## Provenance

The reviewed resident image is:

```text
SHA-256 : 0d64b50b17dcae9318a7c6850ef2d46da84923ccfe0fa9f2611f0287ec59be02
words   : 5123
bytes   : 10246
range   : 0x00004000-0x00006806
```

Legacy compiler evidence:

```text
resident source : 69f3ebdca0583310c9bb6508b25bfdbfe77093bc33f67fe70916050b4168ed30
resident header : d18795d693c9b84ea2504f7a327e47edc55111f76a698fe25164abd95bf1b560
resident object : aaa824ed0e44a4d40aa49808f77ebeffa4eb2ac9dd6e96f8a3ec22d72df6d8f6
producer source : ce7e48b49381836828f1f40f9205c530a7aa368c407463049416030d8b5d974d
producer header : 59c12246a82d0b6341746092cc8facfb374fd8da39db003919ca6c976cdb5e61
producer object : 0f782a4751fb3b47c115d5c7bddb8d1a90ef859335aaf288b9d7754dffbb890a
```

Accepted inert integration anchors:

```text
runtime : a95a212d810b36c75ce96710bc4e33267c561c5ebe7f527b0f9f25408eb3f1ed
BIN     : 30659dddca8b98956d5d89acbc2b321097fa3e4365d20f1a268a1c5b3a83bb82
CUE     : 5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

## Nonclaims

R22 does not yet prove a final hardware-derived clock source.  The SH-2 publishes
reviewed synthetic microsecond milestones through the tear-safe shared clock,
and the MC68EC000 proves due-time behavior against them.

R22 also does not prove:

```text
voice allocation
SCSP slot programming
MIDI-generated audio
polyphony
```

Those begin only after the refill/scheduler service passes on real hardware.
