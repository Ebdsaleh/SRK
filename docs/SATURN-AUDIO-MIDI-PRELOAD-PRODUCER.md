# Saturn Audio MIDI Preload Producer Contract

The legacy SH-ELF compiler and the full Stage-6B standalone image have already
accepted SRK's inert generated MIDI event/tone data. This tranche moves one step
closer to hardware by defining the SH-2 producer that will eventually publish
that data into Sound RAM for an MC68EC000 consumer.

The producer is **not called by the diagnostic yet**.

## Scope

This tranche adds:

- an exact Python representation of the Sound-RAM preload image;
- a generated C89 SH-2 producer;
- explicit READY-last publication ordering;
- read-back validation helpers;
- no MC68EC000 program;
- no SCSP register writes;
- no SMPC SNDON/SNDOFF commands;
- no controller/menu activation;
- no SAROO/card write.

## Canonical preload image

The current deterministic MIDI diagnostic contains 27 events.

The preload image is:

```text
mailbox       12 words
queue         108 words (27 records x 4 words)
tone bank     192 words (3 tones x 64 samples)
total         312 words / 624 bytes
SHA-256       4b9ace091bdbf23fa1536e8b9373604ef57cd172edf506a1e37db9b29cbb2451
```

The SHA is over the logical big-endian word stream:

```text
mailbox words || queue words || tone words
```

It is provenance for the normalized preload content, not a claim that those
three Sound-RAM regions are physically contiguous.

## Queue word encoding

Each existing 8-byte SRKM event becomes four 16-bit Sound-RAM words:

```text
word 0  time_us high 16
word 1  time_us low 16
word 2  opcode << 8 | channel
word 3  data0  << 8 | data1
```

This preserves the existing SRKM big-endian contract without depending on C
struct layout.

## Mailbox publication

The canonical preloaded batch is published as:

```text
magic0          0x5352
magic1          0x4B4D
version         1
flags           READY (0x0001)
write sequence  1
read sequence   0
write index     27
read index      0
capacity        32
queue count     27
last error      0
reserved        0
```

The C producer withdraws READY before touching the tone bank or queue and writes
READY **last** after all other mailbox state is complete. A future 68K consumer
must therefore treat READY as the publication barrier for the batch.

## Hardware boundaries

The producer uses the already accepted SH-2 Sound-RAM aperture:

```text
0x25A00000
```

and the previously allocated relative Sound-RAM regions:

```text
0x00001000-0x000010FF  mailbox
0x00001100-0x000011FF  queue
0x00003000-0x0000317F  tone bank
```

It contains no SCSP MMIO address and no SMPC command address.

## Current execution status

The functions now exist in source:

```text
srk_saturn_midi_preload_publish()
srk_saturn_midi_preload_unpublish()
srk_saturn_midi_preload_is_ready()
```

No production code calls them yet. Therefore pulling/testing this tranche cannot
change the behavior of R17 or any currently generated standalone image.

## Next gate

After the source gate is green:

1. compile this producer with the real legacy SH-ELF GCC backend;
2. link it, still uncalled, into a fresh off-card full standalone build;
3. only after those gates pass should SRK define the MC68EC000 consumer program;
4. active hardware launch remains a later physical revision.

External MIDI input remains out of scope; the target remains deterministic MIDI
file/sequence playback on a standard Saturn.
