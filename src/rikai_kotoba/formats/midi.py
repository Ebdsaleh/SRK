"""Strict, platform-neutral Standard MIDI File parsing for SRK.

The parser intentionally stops at normalized SMF events.  Saturn-specific sound
hardware policy belongs in a later consumer so the same decoded sequence can be
used by diagnostics, Mjolnir and the flight recorder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


MIDI_HEADER_MAGIC = b"MThd"
MIDI_TRACK_MAGIC = b"MTrk"
MIDI_HEADER_MIN_BYTES = 6
MIDI_VLQ_MAX_BYTES = 4


class MidiFormatError(RuntimeError):
    """Raised when a Standard MIDI File is structurally invalid."""


@dataclass(frozen=True)
class MidiHeader:
    format_type: int
    track_count: int
    division: int

    @property
    def uses_smpte_timing(self) -> bool:
        return bool(self.division & 0x8000)

    @property
    def ticks_per_quarter(self) -> int | None:
        if self.uses_smpte_timing:
            return None
        return self.division


@dataclass(frozen=True)
class MidiEvent:
    delta_ticks: int
    tick: int
    kind: str
    status: int
    channel: int | None = None
    data: tuple[int, ...] = ()
    meta_type: int | None = None
    payload: bytes = b""

    @property
    def tempo_us_per_quarter(self) -> int | None:
        if self.kind != "set_tempo" or len(self.payload) != 3:
            return None
        return int.from_bytes(self.payload, "big")

    @property
    def pitch_bend(self) -> int | None:
        if self.kind != "pitch_bend" or len(self.data) != 2:
            return None
        return self.data[0] | (self.data[1] << 7)


@dataclass(frozen=True)
class MidiTrack:
    events: tuple[MidiEvent, ...]


@dataclass(frozen=True)
class MidiFile:
    header: MidiHeader
    tracks: tuple[MidiTrack, ...]


@dataclass(frozen=True)
class MidiMergedEvent:
    track_index: int
    event_index: int
    event: MidiEvent


def _u16_be(data: bytes, offset: int, label: str) -> int:
    end = offset + 2
    if end > len(data):
        raise MidiFormatError(f"truncated {label}")
    return int.from_bytes(data[offset:end], "big")


def _u32_be(data: bytes, offset: int, label: str) -> int:
    end = offset + 4
    if end > len(data):
        raise MidiFormatError(f"truncated {label}")
    return int.from_bytes(data[offset:end], "big")


def _read_vlq(data: bytes, offset: int, end: int, label: str) -> tuple[int, int]:
    value = 0
    count = 0
    while True:
        if offset >= end:
            raise MidiFormatError(f"truncated {label}")
        byte = data[offset]
        offset += 1
        count += 1
        if count > MIDI_VLQ_MAX_BYTES:
            raise MidiFormatError(f"{label} exceeds four-byte SMF VLQ limit")
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            return value, offset


def _require_data_bytes(data: bytes, offset: int, end: int, count: int) -> tuple[tuple[int, ...], int]:
    if offset + count > end:
        raise MidiFormatError("truncated MIDI channel event")
    values = tuple(data[offset : offset + count])
    if any(value & 0x80 for value in values):
        raise MidiFormatError("MIDI channel data byte has status bit set")
    return values, offset + count


def _channel_kind(command: int, data: tuple[int, ...]) -> str:
    if command == 0x80:
        return "note_off"
    if command == 0x90:
        if len(data) == 2 and data[1] == 0:
            return "note_off"
        return "note_on"
    if command == 0xA0:
        return "poly_aftertouch"
    if command == 0xB0:
        return "control_change"
    if command == 0xC0:
        return "program_change"
    if command == 0xD0:
        return "channel_pressure"
    if command == 0xE0:
        return "pitch_bend"
    raise MidiFormatError(f"unsupported MIDI channel status 0x{command:02X}")


def _meta_kind(meta_type: int) -> str:
    return {
        0x01: "text",
        0x02: "copyright",
        0x03: "track_name",
        0x04: "instrument_name",
        0x05: "lyric",
        0x06: "marker",
        0x07: "cue_point",
        0x2F: "end_of_track",
        0x51: "set_tempo",
        0x58: "time_signature",
        0x59: "key_signature",
    }.get(meta_type, "meta")


def _parse_track(data: bytes, start: int, end: int) -> MidiTrack:
    events: list[MidiEvent] = []
    offset = start
    running_status: int | None = None
    tick = 0
    saw_end = False

    while offset < end:
        if saw_end:
            raise MidiFormatError("MIDI track contains bytes after end-of-track event")

        delta, offset = _read_vlq(data, offset, end, "MIDI delta-time")
        tick += delta
        if offset >= end:
            raise MidiFormatError("truncated MIDI event after delta-time")

        first = data[offset]
        if first & 0x80:
            status = first
            offset += 1
            if 0x80 <= status <= 0xEF:
                running_status = status
        else:
            if running_status is None:
                raise MidiFormatError("MIDI running status used before channel status")
            status = running_status

        if 0x80 <= status <= 0xEF:
            command = status & 0xF0
            channel = status & 0x0F
            data_count = 1 if command in (0xC0, 0xD0) else 2
            values, offset = _require_data_bytes(data, offset, end, data_count)
            events.append(
                MidiEvent(
                    delta_ticks=delta,
                    tick=tick,
                    kind=_channel_kind(command, values),
                    status=status,
                    channel=channel,
                    data=values,
                )
            )
            continue

        if status == 0xFF:
            if offset >= end:
                raise MidiFormatError("truncated MIDI meta-event type")
            meta_type = data[offset]
            offset += 1
            length, offset = _read_vlq(data, offset, end, "MIDI meta-event length")
            if offset + length > end:
                raise MidiFormatError("truncated MIDI meta-event payload")
            payload = bytes(data[offset : offset + length])
            offset += length
            kind = _meta_kind(meta_type)
            if meta_type == 0x2F and length != 0:
                raise MidiFormatError("end-of-track meta-event must have zero length")
            if meta_type == 0x51 and length != 3:
                raise MidiFormatError("set-tempo meta-event must contain exactly three bytes")
            events.append(
                MidiEvent(
                    delta_ticks=delta,
                    tick=tick,
                    kind=kind,
                    status=status,
                    meta_type=meta_type,
                    payload=payload,
                )
            )
            if meta_type == 0x2F:
                saw_end = True
            continue

        if status in (0xF0, 0xF7):
            length, offset = _read_vlq(data, offset, end, "MIDI SysEx length")
            if offset + length > end:
                raise MidiFormatError("truncated MIDI SysEx payload")
            payload = bytes(data[offset : offset + length])
            offset += length
            events.append(
                MidiEvent(
                    delta_ticks=delta,
                    tick=tick,
                    kind="sysex" if status == 0xF0 else "sysex_escape",
                    status=status,
                    payload=payload,
                )
            )
            continue

        raise MidiFormatError(f"unsupported SMF status byte 0x{status:02X}")

    if not saw_end:
        raise MidiFormatError("MIDI track is missing end-of-track meta-event")
    return MidiTrack(events=tuple(events))


def parse_midi_bytes(data: bytes) -> MidiFile:
    """Parse one complete Standard MIDI File from bytes."""

    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if len(data) < 14:
        raise MidiFormatError("file is too small to contain an SMF header")
    if data[:4] != MIDI_HEADER_MAGIC:
        raise MidiFormatError("missing MThd header")

    header_length = _u32_be(data, 4, "MIDI header length")
    if header_length < MIDI_HEADER_MIN_BYTES:
        raise MidiFormatError("MIDI header chunk is shorter than six bytes")
    header_end = 8 + header_length
    if header_end > len(data):
        raise MidiFormatError("truncated MIDI header chunk")

    format_type = _u16_be(data, 8, "MIDI format")
    track_count = _u16_be(data, 10, "MIDI track count")
    division = _u16_be(data, 12, "MIDI time division")

    if format_type not in (0, 1, 2):
        raise MidiFormatError(f"unsupported MIDI format {format_type}")
    if track_count < 1:
        raise MidiFormatError("MIDI file declares zero tracks")
    if format_type == 0 and track_count != 1:
        raise MidiFormatError("MIDI format 0 must contain exactly one track")
    if division == 0:
        raise MidiFormatError("MIDI time division must not be zero")

    header = MidiHeader(
        format_type=format_type,
        track_count=track_count,
        division=division,
    )

    tracks: list[MidiTrack] = []
    offset = header_end
    for index in range(track_count):
        if offset + 8 > len(data):
            raise MidiFormatError(f"missing MIDI track chunk {index}")
        if data[offset : offset + 4] != MIDI_TRACK_MAGIC:
            raise MidiFormatError(f"track {index} does not begin with MTrk")
        length = _u32_be(data, offset + 4, f"MIDI track {index} length")
        start = offset + 8
        end = start + length
        if end > len(data):
            raise MidiFormatError(f"truncated MIDI track chunk {index}")
        tracks.append(_parse_track(data, start, end))
        offset = end

    if offset != len(data):
        raise MidiFormatError("unexpected bytes after declared MIDI tracks")

    return MidiFile(header=header, tracks=tuple(tracks))


def parse_midi_file(path: os.PathLike[str] | str) -> MidiFile:
    """Read and parse a Standard MIDI File without modifying it."""

    source = Path(path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise MidiFormatError(f"MIDI source is not a file: {source}")
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise MidiFormatError(f"cannot read MIDI source {source}: {exc}") from exc
    return parse_midi_bytes(data)


def merge_midi_events(midi: MidiFile) -> tuple[MidiMergedEvent, ...]:
    """Return all track events in deterministic absolute-tick order."""

    merged = [
        MidiMergedEvent(track_index, event_index, event)
        for track_index, track in enumerate(midi.tracks)
        for event_index, event in enumerate(track.events)
    ]
    merged.sort(key=lambda item: (item.event.tick, item.track_index, item.event_index))
    return tuple(merged)
