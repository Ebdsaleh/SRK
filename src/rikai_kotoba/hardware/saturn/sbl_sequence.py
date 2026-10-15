"""Native Sega Saturn SDDRV sequence-bank encoding.

This module targets the M6 sequence representation consumed by the Sega Saturn
sound driver's DEC2 decoder.  It intentionally emits a simple, unreferenced and
unreserved stream: fidelity first, compression later.

The on-disc/on-host sequence bank layout is the one used by Sega's SBL samples:
16-bit song count, one 32-bit bank-relative offset per song, then song payloads.
The external sound-area map layout is the Sound Simulator/SBL .MP representation:
one-byte data-id/bank, 24-bit sound-RAM address, 32-bit area size, terminated by
FF FF.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Mapping

from rikai_kotoba.formats.midi import MidiEvent, MidiFile, MidiMergedEvent, merge_midi_events


class SaturnSblSequenceError(RuntimeError):
    """Raised when SMF data cannot be represented by the Sega SDDRV sequencer."""


SBL_AREA_TONE = 0
SBL_AREA_SEQUENCE = 1
SBL_AREA_DSP_PROGRAM = 2
SBL_AREA_DSP_RAM = 3
SBL_AREA_MIXER = 5

_M6_END_OF_TRACK = 0x83
_M6_GATE_EXTENSIONS = ((0x2000, 0x8B), (0x1000, 0x8A), (0x0800, 0x89), (0x0200, 0x88))
_M6_DELTA_EXTENSIONS = ((0x1000, 0x8F), (0x0800, 0x8E), (0x0200, 0x8D), (0x0100, 0x8C))


@dataclass(frozen=True)
class SaturnSblArea:
    data_id: int
    bank: int
    start: int
    size: int


@dataclass(frozen=True)
class SaturnM6DecodedEvent:
    kind: str
    channel: int | None = None
    command: int | None = None
    data0: int = 0
    data1: int = 0
    gate_ticks: int = 0
    step_ticks: int = 0


@dataclass(frozen=True)
class SaturnM6Sequence:
    resolution: int
    tempo_event_count: int
    end_tick: int
    channel_event_count: int
    note_count: int
    song: bytes


@dataclass
class _SourceEvent:
    tick: int
    track_index: int
    event_index: int
    event: MidiEvent
    gate_ticks: int = 0


def _u16(value: int, label: str) -> bytes:
    if not 0 <= value <= 0xFFFF:
        raise SaturnSblSequenceError(f"{label} does not fit 16 bits: {value}")
    return value.to_bytes(2, "big")


def _u24(value: int, label: str) -> bytes:
    if not 0 <= value <= 0xFFFFFF:
        raise SaturnSblSequenceError(f"{label} does not fit 24 bits: {value}")
    return value.to_bytes(3, "big")


def _u32(value: int, label: str) -> bytes:
    if not 0 <= value <= 0xFFFFFFFF:
        raise SaturnSblSequenceError(f"{label} does not fit 32 bits: {value}")
    return value.to_bytes(4, "big")


def encode_sbl_external_area_map(entries: Iterable[SaturnSblArea]) -> bytes:
    """Encode the external .MP form accepted by SND_Init/Sound Simulator data."""

    out = bytearray()
    seen: set[tuple[int, int]] = set()
    for entry in entries:
        if not 0 <= entry.data_id <= 0x0F or not 0 <= entry.bank <= 0x0F:
            raise SaturnSblSequenceError("area-map data id and bank must fit four bits")
        key = (entry.data_id, entry.bank)
        if key in seen:
            raise SaturnSblSequenceError(f"duplicate area-map data id/bank: {key}")
        seen.add(key)
        if not 0 <= entry.start < 0x100000:
            raise SaturnSblSequenceError("Saturn sound-RAM address must fit 20 bits")
        if entry.size <= 0:
            raise SaturnSblSequenceError("area-map size must be positive")
        if entry.start + entry.size > 0x100000:
            raise SaturnSblSequenceError("area-map region exceeds 20-bit sound address space")
        out.append((entry.data_id << 4) | entry.bank)
        out.extend(_u24(entry.start, "area-map start"))
        out.extend(_u32(entry.size, "area-map size"))
    out.extend(b"\xFF\xFF")
    return bytes(out)


def encode_saturn_sequence_bank(songs: Iterable[bytes]) -> bytes:
    """Link one or more already-converted M6 songs into an SDDRV sequence bank."""

    values = tuple(bytes(song) for song in songs)
    if not values:
        raise SaturnSblSequenceError("sequence bank must contain at least one song")
    if len(values) > 0xFFFF:
        raise SaturnSblSequenceError("sequence bank song count exceeds 16 bits")
    header_size = 2 + 4 * len(values)
    offset = header_size
    out = bytearray(_u16(len(values), "sequence-bank song count"))
    for song in values:
        if not song:
            raise SaturnSblSequenceError("sequence bank contains an empty song")
        out.extend(_u32(offset, "sequence-bank song offset"))
        offset += len(song)
    for song in values:
        out.extend(song)
    return bytes(out)


def _tempo_events(midi: MidiFile, end_tick: int) -> tuple[tuple[int, int], ...]:
    by_tick: dict[int, int] = {}
    for merged in merge_midi_events(midi):
        event = merged.event
        if event.kind == "set_tempo":
            tempo = event.tempo_us_per_quarter
            if tempo is None:
                raise SaturnSblSequenceError("invalid SMF tempo event")
            by_tick[event.tick] = tempo
        elif event.kind in {"sysex", "sysex_escape"}:
            raise SaturnSblSequenceError("Sega Saturn sequence conversion rejects SMF SysEx")

    ordered = sorted(by_tick.items())
    if not ordered or ordered[0][0] != 0:
        ordered.insert(0, (0, 500_000))

    result: list[tuple[int, int]] = []
    for index, (tick, tempo) in enumerate(ordered):
        if not 200_000 <= tempo <= 1_500_000:
            raise SaturnSblSequenceError(
                f"tempo {tempo} usec/quarter is outside SDDRV 40..300 BPM range"
            )
        next_tick = ordered[index + 1][0] if index + 1 < len(ordered) else end_tick
        if next_tick < tick:
            raise SaturnSblSequenceError("tempo events are not monotonic")
        result.append((next_tick - tick, tempo))
    return tuple(result)


def _channel_sources(midi: MidiFile) -> tuple[list[_SourceEvent], int]:
    if midi.header.format_type != 1:
        raise SaturnSblSequenceError("Sega Standard MIDI converter workflow requires SMF type 1")
    resolution = midi.header.ticks_per_quarter
    if resolution is None:
        raise SaturnSblSequenceError("Sega Saturn sequence conversion requires PPQN timing")
    if not 24 <= resolution <= 960:
        raise SaturnSblSequenceError("SDDRV sequence resolution must be within 24..960")

    end_tick = max(
        (event.tick for track in midi.tracks for event in track.events if event.kind == "end_of_track"),
        default=0,
    )
    sources: list[_SourceEvent] = []
    pending: dict[tuple[int, int], deque[_SourceEvent]] = defaultdict(deque)

    supported = {
        "note_on",
        "note_off",
        "poly_aftertouch",
        "control_change",
        "program_change",
        "channel_pressure",
        "pitch_bend",
    }
    for merged in merge_midi_events(midi):
        event = merged.event
        if event.channel is None:
            continue
        if event.kind not in supported:
            continue
        if event.kind == "note_off":
            note = event.data[0]
            queue = pending[(event.channel, note)]
            if not queue:
                raise SaturnSblSequenceError(
                    f"unmatched Note Off at tick {event.tick}: ch={event.channel} note={note}"
                )
            start = queue.popleft()
            start.gate_ticks = event.tick - start.tick
            continue

        source = _SourceEvent(
            tick=event.tick,
            track_index=merged.track_index,
            event_index=merged.event_index,
            event=event,
        )
        sources.append(source)
        if event.kind == "note_on":
            pending[(event.channel, event.data[0])].append(source)

    dangling = [item for queue in pending.values() for item in queue]
    if dangling:
        first = min(dangling, key=lambda item: (item.tick, item.track_index, item.event_index))
        raise SaturnSblSequenceError(
            f"Note On has no matching Note Off: ch={first.event.channel} "
            f"note={first.event.data[0]} tick={first.tick}"
        )
    sources.sort(key=lambda item: (item.tick, item.track_index, item.event_index))
    return sources, end_tick


def _extension_bytes(value: int, table: tuple[tuple[int, int], ...], base_max: int) -> tuple[bytes, int]:
    if value < 0:
        raise SaturnSblSequenceError("negative Saturn sequence time")
    remaining = value
    out = bytearray()
    while remaining > base_max:
        chosen = None
        for amount, command in table:
            if amount <= remaining:
                chosen = (amount, command)
                break
        if chosen is None:
            raise SaturnSblSequenceError(f"cannot encode Saturn sequence time {value}")
        amount, command = chosen
        out.append(command)
        remaining -= amount
    return bytes(out), remaining


def _encode_note(event: _SourceEvent, step_ticks: int) -> bytes:
    channel = event.event.channel
    assert channel is not None
    note, velocity = event.event.data
    if not 0 <= channel <= 15:
        raise SaturnSblSequenceError("SMF channel exceeds Saturn MIDI port-0 range")
    gate_prefix, gate = _extension_bytes(event.gate_ticks, _M6_GATE_EXTENSIONS, 0x1FF)
    step_prefix, step = _extension_bytes(step_ticks, _M6_DELTA_EXTENSIONS, 0x1FF)
    status = channel | (((step >> 8) & 1) << 5) | (((gate >> 8) & 1) << 6)
    return gate_prefix + step_prefix + bytes((status, note, velocity, gate & 0xFF, step & 0xFF))


def _encode_midi_event(event: _SourceEvent, step_ticks: int) -> bytes:
    midi = event.event
    channel = midi.channel
    assert channel is not None
    if not 0 <= channel <= 15:
        raise SaturnSblSequenceError("SMF channel exceeds Saturn MIDI port-0 range")
    prefix, step = _extension_bytes(step_ticks, _M6_DELTA_EXTENSIONS, 0xFF)

    command = midi.status & 0xF0
    status = command | channel
    if midi.kind in {"poly_aftertouch", "control_change"}:
        data = bytes((status, midi.data[0], midi.data[1], step))
    elif midi.kind in {"program_change", "channel_pressure"}:
        data = bytes((status, midi.data[0], step))
    elif midi.kind == "pitch_bend":
        # DEC2's M6 path consumes the seven-bit MSB only, matching the converter's
        # pitch-bend compression mode and the current SDDRV decoder.
        data = bytes((status, midi.data[1], step))
    else:
        raise SaturnSblSequenceError(f"cannot encode Saturn M6 event {midi.kind}")
    return prefix + data


def compile_midi_to_saturn_m6(midi: MidiFile) -> SaturnM6Sequence:
    """Convert an SMF type-1 song to the native M6 song payload consumed by SDDRV."""

    resolution = midi.header.ticks_per_quarter
    if resolution is None:
        raise SaturnSblSequenceError("Sega Saturn sequence conversion requires PPQN timing")
    sources, end_tick = _channel_sources(midi)
    tempos = _tempo_events(midi, end_tick)

    tempo_blob = bytearray()
    for step, tempo in tempos:
        tempo_blob.extend(_u32(step, "tempo step"))
        tempo_blob.extend(_u32(tempo, "tempo value"))
    track_start = 8 + len(tempo_blob)
    if track_start > 0xFFFF:
        raise SaturnSblSequenceError("tempo track makes M6 song header exceed 16-bit offset")

    track_blob = bytearray()
    note_count = 0
    for index, source in enumerate(sources):
        next_tick = sources[index + 1].tick if index + 1 < len(sources) else end_tick
        if next_tick < source.tick:
            raise SaturnSblSequenceError("channel events are not monotonic")
        step = next_tick - source.tick
        if source.event.kind == "note_on":
            track_blob.extend(_encode_note(source, step))
            note_count += 1
        else:
            track_blob.extend(_encode_midi_event(source, step))
    track_blob.append(_M6_END_OF_TRACK)

    # Word +2 is emitted by Sega-produced M6 data as the number of tempo entries.
    # DEC2 locates tempo data by offsets, so this field is informational for SDDRV.
    song = bytearray()
    song.extend(_u16(resolution, "sequence resolution"))
    song.extend(_u16(len(tempos), "tempo event count"))
    song.extend(_u16(track_start, "track start offset"))
    song.extend(b"\x00\x00")  # no tempo loop
    song.extend(tempo_blob)
    song.extend(track_blob)
    return SaturnM6Sequence(
        resolution=resolution,
        tempo_event_count=len(tempos),
        end_tick=end_tick,
        channel_event_count=len(sources),
        note_count=note_count,
        song=bytes(song),
    )


def decode_uncompressed_saturn_m6(song: bytes) -> tuple[SaturnM6DecodedEvent, ...]:
    """Decode SRK's uncompressed M6 subset using the same rules as Sega DEC2.ASM."""

    if len(song) < 9:
        raise SaturnSblSequenceError("M6 song is truncated")
    track_start = int.from_bytes(song[4:6], "big")
    if not 8 <= track_start < len(song):
        raise SaturnSblSequenceError("M6 track offset is invalid")
    pos = track_start
    gate_ext = 0
    step_ext = 0
    out: list[SaturnM6DecodedEvent] = []
    while pos < len(song):
        command = song[pos]
        pos += 1
        if command <= 0x7F:
            if pos + 4 > len(song):
                raise SaturnSblSequenceError("truncated M6 note")
            note, velocity, gate_low, step_low = song[pos : pos + 4]
            pos += 4
            gate = gate_ext + (((command >> 6) & 1) << 8) + gate_low
            step = step_ext + (((command >> 5) & 1) << 8) + step_low
            out.append(
                SaturnM6DecodedEvent(
                    "note_on",
                    channel=command & 0x1F,
                    command=0x90,
                    data0=note,
                    data1=velocity,
                    gate_ticks=gate,
                    step_ticks=step,
                )
            )
            gate_ext = step_ext = 0
            continue
        if command == _M6_END_OF_TRACK:
            out.append(SaturnM6DecodedEvent("end_of_track"))
            break
        gate_match = next((amount for amount, code in _M6_GATE_EXTENSIONS if code == command), None)
        if gate_match is not None:
            gate_ext += gate_match
            continue
        step_match = next((amount for amount, code in _M6_DELTA_EXTENSIONS if code == command), None)
        if step_match is not None:
            step_ext += step_match
            continue
        if 0xA0 <= command <= 0xBF:
            if pos + 3 > len(song):
                raise SaturnSblSequenceError("truncated M6 two-data MIDI event")
            data0, data1, step = song[pos : pos + 3]
            pos += 3
            if data0 & 0x80:
                raise SaturnSblSequenceError("compressed step omission is outside SRK M6 subset")
            out.append(
                SaturnM6DecodedEvent(
                    "midi",
                    channel=command & 0x0F,
                    command=command & 0xF0,
                    data0=data0,
                    data1=data1,
                    step_ticks=step_ext + step,
                )
            )
            step_ext = 0
            continue
        if 0xC0 <= command <= 0xDF:
            if pos + 2 > len(song):
                raise SaturnSblSequenceError("truncated M6 one-data MIDI event")
            data0, step = song[pos : pos + 2]
            pos += 2
            if data0 & 0x80:
                raise SaturnSblSequenceError("compressed step omission is outside SRK M6 subset")
            out.append(
                SaturnM6DecodedEvent(
                    "midi",
                    channel=command & 0x0F,
                    command=command & 0xF0,
                    data0=data0,
                    step_ticks=step_ext + step,
                )
            )
            step_ext = 0
            continue
        if 0xE0 <= command <= 0xEF:
            if pos + 2 > len(song):
                raise SaturnSblSequenceError("truncated M6 pitch-bend event")
            data1, step = song[pos : pos + 2]
            pos += 2
            if data1 & 0x80:
                raise SaturnSblSequenceError("compressed step omission is outside SRK M6 subset")
            out.append(
                SaturnM6DecodedEvent(
                    "midi",
                    channel=command & 0x0F,
                    command=0xE0,
                    data1=data1,
                    step_ticks=step_ext + step,
                )
            )
            step_ext = 0
            continue
        raise SaturnSblSequenceError(f"unsupported/compressed M6 command 0x{command:02X}")
    return tuple(out)
