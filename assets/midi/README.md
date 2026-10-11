# SRK third-party MIDI source assets

This directory contains third-party MIDI source material used to exercise SRK's general MIDI parsing, scheduling and future Saturn playback path after the accepted R19 silent 27-record MC68EC000 proof.

These files are source fixtures. Preserve them byte-for-byte. Tests, conversions, SRKM programs, tone-bank experiments and Saturn deployment assets must be generated into separate output/workspace paths rather than modifying these originals in place.

The license notices below apply to the corresponding third-party assets only; they do not replace or change SRK's project license.

## Double Impact MIDI Pack

The supplied upstream archive is represented in Git as five lossless ASCII base64 transport segments:

```text
assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip.b64.000
assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip.b64.001
assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip.b64.002
assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip.b64.003
assets/midi/cc0/double-impact/dbimmidi-oga-mid.zip.b64.004
```

Concatenating those files in numeric order and base64-decoding the resulting ASCII stream reproduces the original supplied ZIP byte-for-byte. The transport envelope exists only to avoid binary mutation by repository-upload tooling; it is not a conversion of the MIDI data.

Transport segment sizes are locked as:

```text
.000 : 15113 ASCII bytes
.001 : 15113 ASCII bytes
.002 : 15113 ASCII bytes
.003 :  7556 ASCII bytes
.004 :  7557 ASCII bytes
```

Upstream page:

```text
https://opengameart.org/content/double-impact-midi-pack
```

OpenGameArt lists the pack as **CC0**.

The upstream copyright/attribution notice is:

> Double Impact MIDI Pack by continuum.mid, Matzu, R0rque, Korp, and ZeMystic.

The page uploader/author account is `northivanastan`; the contributor credit above is the pack's stated attribution notice.

Supplied archive provenance after decoding the repository transport:

```text
Filename : dbimmidi-oga-mid.zip
Bytes    : 45337
SHA-256  : c665dd930726d25305f8c8e104a235399a04a04cf50d2f3eda251dd7be8d658c
```

The decoded archive's MIDI members and hashes are:

```text
midis/E1M2, E4M3 - Matzu - Space Spectre.mid
  bytes   36680
  SHA-256 984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01

midis/E1M3, E4M2 - R0rque - Fight Harder...  To Obtain A Better Victory!.mid
  bytes   60593
  SHA-256 2bfe003662d065f21d424441cb2beb1ec767f40c2c08b77c7b27e2c0f090feb8

midis/E1M4, E4M4 - continuum.mid - Deliberate Concealment.mid
  bytes   18444
  SHA-256 3a64c328f79fcdc61b725c91cc515db4a8723b177c4b82d46e775cc52884a5e8

midis/E1M5, E4M5 - Korp - Main Code.mid
  bytes   74604
  SHA-256 cefe563e1035d06b2710b0cf71d7fbb8f4bfa60c19a60cddaa801ab01fc3f6db

midis/E1M6, E4M6 - ZeMystic - Andromeda.mid
  bytes   22199
  SHA-256 c9c1409062221a4784b27607f804c406200b362fbe54dc822937d05690fd728e

midis/E1M7, E4M7 - Korp - Ambiguity.mid
  bytes   58512
  SHA-256 2b1a3569765292e7ddb0d2f9bac181ec00027139a8d642cd4f2abb453c3767ea

midis/E1M8, E4M8 - continuum.mid -  Vs. The Assault Quindecapod.mid
  bytes   17398
  SHA-256 1f12801b85594de730bdc1c7043f3de22ad0ddaa9955de4dbfb4d62a99b89458

midis/E1M9, E4M9 - continuum.mid - The Deepest Secrets.mid
  bytes   13157
  SHA-256 10e4988a40ad1a7c0ae21680c251683c398dd80ae790477f0e0e68db980ef69b

midis/E4M1 - continuum.mid - Liberate the Stars.mid
  bytes   18529
  SHA-256 48ad457f927172c3570777af6ef9135c1b41b53a04a493680d7d6be10f0780af

midis/INTER - Korp - Resprenselessness.mid
  bytes   76766
  SHA-256 66460ef416f6d97ddbfc13ecd2b9cf5fa1c499a54b4e6f88310ec318e3d7b64b

midis/TITLE - continuum.mid - Triple Impact.mid
  bytes   815
  SHA-256 d309c64f2e75ed51096223aa4b8030eaf233ae55301894416abee67c37f87dcc
```

## MIDI Town Theme Melody

Repository source:

```text
assets/midi/cc0/melody-town-theme/Melody Town Theme.mid
```

Upstream page:

```text
https://opengameart.org/content/midi-town-theme-melody
```

OpenGameArt lists the asset as **CC0** and identifies the author as **CleytonKauffman**.

Supplied file provenance:

```text
Filename : Melody Town Theme.mid
Bytes    : 1333
SHA-256  : 9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041
```

The supplied SMF is format 1, uses 96 ticks per beat, contains three tracks, and includes a musical track named `Flute`.

## Intended SRK use

These assets are not R19 inputs and do not alter any accepted physical baseline.

They are intended for the next MIDI-driver stages:

```text
general resident decoder
-> arbitrary MIDI-derived command programs
-> timing/state validation
-> voice allocation
-> first MIDI-driven SCSP note
-> polyphony and multi-channel playback
```

`Melody Town Theme.mid` is a useful early real-world single-instrument fixture. The Double Impact pack then provides a broader multi-track corpus for parser, scheduling and compatibility work.

> Source is immutable; derived output is disposable and reproducible.
