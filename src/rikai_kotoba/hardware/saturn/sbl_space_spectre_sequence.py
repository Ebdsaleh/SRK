"""Compile the locked Space Spectre SMF to a native Sega Saturn SDDRV sequence bank.

This is the offline production-style path used for authored music: Standard MIDI
is converted once on the host into M6 sequence data, linked into a sequence bank,
and later handed to SDDRV's native sequencer.  No Direct-MIDI event streaming is
part of this conversion.

The Saturn sound driver does not infer General MIDI channel-10 percussion.  A
commercial-style conversion therefore also authors the tone-bank routing into the
sequence: every note-bearing melodic channel selects tone bank 0, while MIDI
channel 10 selects tone bank 1 and voice/program 0.  This replaces the SH-2-side
"priming" commands used by the obsolete Direct-MIDI prototype.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
import json
import os

from rikai_kotoba.formats.midi import MidiEvent, MidiFile, MidiTrack, parse_midi_bytes
from .midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_BYTES,
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_MEMBER,
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
    load_srk_saturn_midi_68k_r26_space_spectre_bytes,
)
from .sbl_sequence import (
    SaturnM6Sequence,
    compile_midi_to_saturn_m6,
    decode_uncompressed_saturn_m6,
    encode_saturn_sequence_bank,
)


class SaturnSpaceSpectreSequenceError(RuntimeError):
    """Raised when the locked song cannot be converted reproducibly."""


MANIFEST_NAME = "SRK_SPACE_SPECTRE_SEQUENCE.json"
BANK_NAME = "SPACESEQ.BNK"
EXPECTED_NOTE_COUNT = 4381
PERCUSSION_CHANNEL = 9
PERCUSSION_TONE_BANK = 1
PERCUSSION_PROGRAM = 0
MELODIC_TONE_BANK = 0
TONE_BANK_CONTROLLER = 32


@dataclass(frozen=True)
class SaturnSpaceSpectreSequenceResult:
    output_directory: Path
    bank_path: Path
    manifest_path: Path
    source_sha256: str
    song_sha256: str
    bank_sha256: str
    source_bytes: int
    song_bytes: int
    bank_bytes: int
    format_type: int
    track_count: int
    resolution: int
    tempo_event_count: int
    end_tick: int
    channel_event_count: int
    note_count: int
    tone_bank_bindings: tuple[tuple[int, int], ...]


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _note_channels(midi: MidiFile) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                event.channel
                for track in midi.tracks
                for event in track.events
                if event.kind == "note_on" and event.channel is not None
            }
        )
    )


def _bind_saturn_tone_banks(midi: MidiFile) -> tuple[MidiFile, tuple[tuple[int, int], ...]]:
    """Author SDDRV tone-bank routing into a copy of the parsed SMF event model.

    CC32 is the Sega driver's tone-bank select.  The original SMF remains
    untouched; this is equivalent to the bank setup a Saturn sound programmer
    would author while preparing the converted sequence and tone-bank assets.
    """

    channels = _note_channels(midi)
    if not channels:
        raise SaturnSpaceSpectreSequenceError("Space Spectre contains no note-bearing channels")
    bindings = tuple(
        (channel, PERCUSSION_TONE_BANK if channel == PERCUSSION_CHANNEL else MELODIC_TONE_BANK)
        for channel in channels
    )
    bank_for = dict(bindings)

    tracks: list[MidiTrack] = []
    for track_index, track in enumerate(midi.tracks):
        events: list[MidiEvent] = []
        if track_index == 0:
            # Put explicit bank routing before the source's tick-zero program and
            # note events.  This makes the converted bank self-contained: the SH-2
            # only starts a sequence and never has to prime MIDI state manually.
            for channel, bank in bindings:
                events.append(
                    MidiEvent(
                        delta_ticks=0,
                        tick=0,
                        kind="control_change",
                        status=0xB0 | channel,
                        channel=channel,
                        data=(TONE_BANK_CONTROLLER, bank),
                    )
                )
                if channel == PERCUSSION_CHANNEL:
                    events.append(
                        MidiEvent(
                            delta_ticks=0,
                            tick=0,
                            kind="program_change",
                            status=0xC0 | channel,
                            channel=channel,
                            data=(PERCUSSION_PROGRAM,),
                        )
                    )

        for event in track.events:
            replacement = event
            if event.channel in bank_for:
                if (
                    event.kind == "control_change"
                    and len(event.data) == 2
                    and event.data[0] == TONE_BANK_CONTROLLER
                ):
                    replacement = replace(event, data=(TONE_BANK_CONTROLLER, bank_for[event.channel]))
                elif event.kind == "program_change" and event.channel == PERCUSSION_CHANNEL:
                    replacement = replace(event, data=(PERCUSSION_PROGRAM,))
            events.append(replacement)
        tracks.append(MidiTrack(events=tuple(events)))

    return MidiFile(header=midi.header, tracks=tuple(tracks)), bindings


def _verify_roundtrip(
    sequence: SaturnM6Sequence,
    bindings: tuple[tuple[int, int], ...],
) -> None:
    decoded = decode_uncompressed_saturn_m6(sequence.song)
    notes = sum(1 for event in decoded if event.kind == "note_on")
    endings = sum(1 for event in decoded if event.kind == "end_of_track")
    if notes != EXPECTED_NOTE_COUNT:
        raise SaturnSpaceSpectreSequenceError(
            f"native M6 round-trip note count changed: expected {EXPECTED_NOTE_COUNT}, got {notes}"
        )
    if endings != 1:
        raise SaturnSpaceSpectreSequenceError(
            f"native M6 round-trip must contain exactly one end-of-track marker, got {endings}"
        )

    bank_selects = {
        (event.channel, event.data1)
        for event in decoded
        if event.kind == "midi"
        and event.command == 0xB0
        and event.data0 == TONE_BANK_CONTROLLER
    }
    missing = [binding for binding in bindings if binding not in bank_selects]
    if missing:
        raise SaturnSpaceSpectreSequenceError(
            f"native M6 round-trip lost tone-bank bindings: {missing}"
        )

    if PERCUSSION_CHANNEL in dict(bindings):
        drum_program = any(
            event.kind == "midi"
            and event.command == 0xC0
            and event.channel == PERCUSSION_CHANNEL
            and event.data0 == PERCUSSION_PROGRAM
            for event in decoded
        )
        if not drum_program:
            raise SaturnSpaceSpectreSequenceError(
                "native M6 round-trip lost channel-10 drum program binding"
            )


def build_space_spectre_native_sequence(
    output_directory: os.PathLike[str] | str,
    *,
    repository_root: os.PathLike[str] | str | None = None,
) -> SaturnSpaceSpectreSequenceResult:
    """Create a fresh off-card Saturn-native sequence bank for the complete song."""

    output = _canonical(output_directory)
    if output.exists():
        raise SaturnSpaceSpectreSequenceError(
            f"output already exists; refusing overwrite: {output}"
        )

    repo = None if repository_root is None else _canonical(repository_root)
    source = load_srk_saturn_midi_68k_r26_space_spectre_bytes(repo)
    source_sha = _sha(source)
    if len(source) != SATURN_MIDI_68K_R26_SPACE_SPECTRE_BYTES:
        raise SaturnSpaceSpectreSequenceError("locked Space Spectre byte count changed")
    if source_sha != SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256:
        raise SaturnSpaceSpectreSequenceError("locked Space Spectre SHA-256 changed")

    midi = parse_midi_bytes(source)
    if midi.header.format_type != 1:
        raise SaturnSpaceSpectreSequenceError(
            f"Space Spectre is no longer SMF type 1: {midi.header.format_type}"
        )
    resolution = midi.header.ticks_per_quarter
    if resolution is None:
        raise SaturnSpaceSpectreSequenceError("Space Spectre unexpectedly uses SMPTE timing")

    authored_midi, bindings = _bind_saturn_tone_banks(midi)
    sequence = compile_midi_to_saturn_m6(authored_midi)
    if sequence.note_count != EXPECTED_NOTE_COUNT:
        raise SaturnSpaceSpectreSequenceError(
            f"Space Spectre native note count changed: expected {EXPECTED_NOTE_COUNT}, "
            f"got {sequence.note_count}"
        )
    _verify_roundtrip(sequence, bindings)

    bank = encode_saturn_sequence_bank((sequence.song,))
    if int.from_bytes(bank[0:2], "big") != 1 or int.from_bytes(bank[2:6], "big") != 6:
        raise SaturnSpaceSpectreSequenceError("one-song sequence-bank header is invalid")
    if bank[6:] != sequence.song:
        raise SaturnSpaceSpectreSequenceError("sequence-bank payload/link offset is invalid")

    song_sha = _sha(sequence.song)
    bank_sha = _sha(bank)
    manifest = {
        "schema": "srk.saturn.sbl-space-spectre-sequence.v2",
        "source": {
            "member": SATURN_MIDI_68K_R26_SPACE_SPECTRE_MEMBER,
            "bytes": len(source),
            "sha256": source_sha,
            "smf_format": midi.header.format_type,
            "track_count": midi.header.track_count,
            "ticks_per_quarter": resolution,
        },
        "native_sequence": {
            "encoding": "sega-sddrv-m6",
            "compression": "none",
            "tempo_event_count": sequence.tempo_event_count,
            "end_tick": sequence.end_tick,
            "channel_event_count": sequence.channel_event_count,
            "note_count": sequence.note_count,
            "song_bytes": len(sequence.song),
            "song_sha256": song_sha,
            "tone_bank_controller": TONE_BANK_CONTROLLER,
            "tone_bank_bindings": [
                {"channel_zero_based": channel, "bank": bank_number}
                for channel, bank_number in bindings
            ],
            "percussion_channel_zero_based": PERCUSSION_CHANNEL,
            "percussion_program": PERCUSSION_PROGRAM,
        },
        "sequence_bank": {
            "filename": BANK_NAME,
            "song_count": 1,
            "first_song_offset": 6,
            "bytes": len(bank),
            "sha256": bank_sha,
        },
        "policy": {
            "playback_path": "Sega SDDRV native sequence",
            "direct_midi_streaming": False,
            "sh2_midi_priming": False,
            "host_conversion_only": True,
            "saroo_writes": False,
            "source_modified": False,
        },
    }

    output.mkdir(parents=True, exist_ok=False)
    bank_path = output / BANK_NAME
    manifest_path = output / MANIFEST_NAME
    try:
        bank_path.write_bytes(bank)
        _write_json(manifest_path, manifest)
    except Exception:
        # This directory did not exist before this function.  Clean only our own
        # incomplete fresh output; never touch caller/source data.
        for path in (manifest_path, bank_path):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        try:
            output.rmdir()
        except OSError:
            pass
        raise

    if bank_path.read_bytes() != bank:
        raise SaturnSpaceSpectreSequenceError("native sequence bank changed after write")
    written_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if written_manifest != manifest:
        raise SaturnSpaceSpectreSequenceError("native sequence manifest changed after write")

    return SaturnSpaceSpectreSequenceResult(
        output_directory=output,
        bank_path=bank_path,
        manifest_path=manifest_path,
        source_sha256=source_sha,
        song_sha256=song_sha,
        bank_sha256=bank_sha,
        source_bytes=len(source),
        song_bytes=len(sequence.song),
        bank_bytes=len(bank),
        format_type=midi.header.format_type,
        track_count=midi.header.track_count,
        resolution=resolution,
        tempo_event_count=sequence.tempo_event_count,
        end_tick=sequence.end_tick,
        channel_event_count=sequence.channel_event_count,
        note_count=sequence.note_count,
        tone_bank_bindings=bindings,
    )
