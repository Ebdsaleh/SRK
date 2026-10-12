# Saturn MIDI / 68K R23 Physical Acceptance

R23 is the first SRK milestone that physically proves a MIDI event can travel through the resident MC68EC000 service into the Saturn SCSP and produce audible sound on real hardware.

## Accepted hardware result

The guarded R23 candidate was run on a real Sega Saturn through SAROO from the fresh destination:

```text
saroo/ISO/TEST/SRK-Diagnostics-R23
```

The physical run reached the successful terminal boundary after the 32+2 scheduler/refill proof, SCSP slot-0 key-on verification, bounded audible hold, scheduled Note Off, SCSP key-off verification, voice-state verification, and full final MIDI-state comparison.

The user independently confirmed that an audible tone was produced. The captured recording also contains the tone during the proof interval.

R23 is therefore accepted as a physical MIDI -> resident MC68EC000 -> SCSP audio-path proof.

## Physical evidence

```text
Recording : SRK-DIAG(20261012-015302).mp4
Bytes     : 5335515
Duration  : 25.466667 seconds
Video     : 464x848 @ 30 fps
Audio     : AAC stereo, 44100 Hz
SHA-256   : 84641c8c62ee8c4cee55119759b402d1f9aac5c58be45d48bd1ffb6b533058c5
```

Audio inspection found a stable spectral component around 440 Hz during the proof. This is consistent with the current 100-sample direct-PCM diagnostic oscillator at the R23 base SCSP pitch setting.

## What R23 proves

R23 physically proves:

- the accepted R22A queue/refill/timestamp service remains functional after adding the audio path;
- the SH-2 can install and start the R23 resident MC68EC000 service;
- MIDI Note On reaches the resident service;
- the resident service allocates its owned voice and updates the voice-state ledger;
- the resident service writes the intended SCSP slot-0 key-on state;
- the SH-2 can read back and verify the SCSP slot state;
- the Saturn produces real audible output from that MIDI-driven key-on;
- the scheduled MIDI Note Off reaches the resident service;
- the resident service clears the physical SCSP voice;
- key-off state is visible to the SH-2 proof;
- final MIDI state remains coherent after the complete 32+2 proof.

## Important pitch qualification

The R23 event uses MIDI note 60, but R23 must **not** be described as proving calibrated MIDI note pitch.

The current proof waveform is a fixed 100-sample direct-PCM oscillator, and note 60 maps to the R23 base SCSP pitch value. The physical recording measures approximately 440 Hz. Therefore R23 proves routing, scheduling, allocation, key-on, audibility, and key-off; it does not yet prove that MIDI note numbers map to musically correct frequencies.

Musical pitch calibration is explicitly deferred to R24.

## Accepted R23 candidate anchors

```text
Manifest:
34a45a49bdb143dc2c1a8996c5e55b159e800df27011ac6ca36aec201d4d54c3

Build report:
fbfe4ac87965fdb0411da3e25f9a6a705be73b7a6b3d8b83d7e8e5031b2096f1

Audio image:
cb172de4e984dd50fcec195c310cb2945abb10bdaa561d31d52062b7e79038a1

Runtime after:
993dfdda0c69e8ba1f4cb84669af2e92252f60cfa787d531e8f2a163b54bbaad

Proof header:
051b46d57d0dafd63399a319cf9f6186e0f6946e5dc6525c1b4457795fef261b

Proof source:
c037a0306bc39c10ff16408826a5ae438327295285929fd05895827adbdbbace

Deploy BIN:
278099a14985a0ad2e5e3b48a5847cefb5e80afc624974509b10f9c4327d6cb6

Deploy CUE:
5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950
```

Whole-card guard used for the accepted deployment:

```text
d6c57f8ff1c90e7b12c73986718b3a840969b8c32c84545916496eae64080a0f
```

Deployment passed both the exact pre-write whole-card comparison and the post-write whole-card audit, with only the fresh R23 directory, BIN, and CUE added.

## Immutability

R23 is now an immutable physical baseline.

Do not overwrite or redeploy `SRK-Diagnostics-R23`. Future audio/MIDI work must use fresh revisions and fresh SAROO destinations.

## R24 direction

R24 moves from a single diagnostic oscillator event to actual Standard MIDI File playback.

The first target is the repository's CC0 `Melody Town Theme.mid`. R24 must add at least:

- real SMF-derived event scheduling and tempo handling;
- continuous monotonic hardware time rather than display-poll timing;
- repeated queue refills across the complete song;
- musically calibrated MIDI-note pitch;
- at least two simultaneous SCSP voices for the target file's overlaps;
- deterministic Note On/Note Off ownership and release;
- end-to-end playback of the real `.mid` file on Saturn hardware.
