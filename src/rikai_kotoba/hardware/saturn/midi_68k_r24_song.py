"""R24 real-SMF playback contract for the first complete Saturn MIDI song.

R23 physically proved one MIDI Note On/Off can cross the resident MC68EC000
service and key SCSP slot 0 on real hardware.  R24 deliberately stops using
synthetic proof programs as its source of truth: this module profiles and
batches a real SRK Standard MIDI File through the already accepted generic
SMF -> schedule -> SRKM v1 pipeline.

The first reference song is the repository's CC0 ``Melody Town Theme.mid``.
Nothing in this module mutates the source asset.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os

from rikai_kotoba.core.midi_sequence import build_midi_tempo_map
from rikai_kotoba.formats.midi import parse_midi_file
from .midi_bridge import SATURN_MIDI_QUEUE_CAPACITY
from .midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
    compile_saturn_midi_program,
)


SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH = Path(
    "assets/midi/cc0/melody-town-theme/Melody Town Theme.mid"
)
SATURN_MIDI_68K_R24_REFERENCE_SHA256 = (
    "9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041"
)
SATURN_MIDI_68K_R24_REFERENCE_FORMAT = 1
SATURN_MIDI_68K_R24_REFERENCE_TRACKS = 3
SATURN_MIDI_68K_R24_REFERENCE_PPQN = 96
SATURN_MIDI_68K_R24_REFERENCE_TEMPO_US_PER_QUARTER = 845070
SATURN_MIDI_68K_R24_REFERENCE_RECORDS = 310
SATURN_MIDI_68K_R24_REFERENCE_DURATION_US = 108151354
SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON = 140
SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF = 140
SATURN_MIDI_68K_R24_REFERENCE_CONTROL_CHANGE = 23
SATURN_MIDI_68K_R24_REFERENCE_PROGRAM_CHANGE = 3
SATURN_MIDI_68K_R24_REFERENCE_PITCH_BEND = 4
SATURN_MIDI_68K_R24_REFERENCE_NOTE_MIN = 71
SATURN_MIDI_68K_R24_REFERENCE_NOTE_MAX = 86
SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY = 2
SATURN_MIDI_68K_R24_REFERENCE_BATCHES = 10
SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS = 22
SATURN_MIDI_68K_R24_REFERENCE_OVERLAP_TIMES_US = (
    30404914,
    41813359,
    84480591,
    95889036,
)


class SaturnMidi68KR24SongError(RuntimeError):
    """Raised when a real-SMF R24 song violates the reviewed playback contract."""


@dataclass(frozen=True)
class SaturnMidi68KR24Batch:
    sequence: int
    first_record_index: int
    records: tuple[SaturnMidiRecord, ...]

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def first_time_us(self) -> int:
        return self.records[0].time_us

    @property
    def last_time_us(self) -> int:
        return self.records[-1].time_us


@dataclass(frozen=True)
class SaturnMidi68KR24SongProfile:
    source_path: Path
    source_sha256: str
    format_type: int
    track_count: int
    ticks_per_quarter: int
    tempo_us_per_quarter: int
    program: SaturnMidiProgram
    batches: tuple[SaturnMidi68KR24Batch, ...]
    opcode_counts: tuple[tuple[SaturnMidiOpcode, int], ...]
    note_min: int
    note_max: int
    peak_polyphony: int
    overlap_times_us: tuple[int, ...]

    @property
    def record_count(self) -> int:
        return len(self.program.records)

    @property
    def duration_us(self) -> int:
        return self.program.duration_us


@dataclass(frozen=True)
class _PolyphonyProfile:
    note_min: int
    note_max: int
    peak_polyphony: int
    overlap_times_us: tuple[int, ...]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def batch_saturn_midi_r24_program(
    program: SaturnMidiProgram,
    *,
    capacity: int = SATURN_MIDI_QUEUE_CAPACITY,
) -> tuple[SaturnMidi68KR24Batch, ...]:
    """Split one chronological SRKM program into strict producer queue batches."""

    if capacity < 1 or capacity > SATURN_MIDI_QUEUE_CAPACITY:
        raise SaturnMidi68KR24SongError(
            f"R24 batch capacity must be within 1..{SATURN_MIDI_QUEUE_CAPACITY}"
        )
    if not program.records:
        raise SaturnMidi68KR24SongError("R24 song has no SRKM records")

    result: list[SaturnMidi68KR24Batch] = []
    for start in range(0, len(program.records), capacity):
        sequence = len(result) + 1
        if sequence > 0xFFFF:
            raise SaturnMidi68KR24SongError("R24 batch sequence exceeds mailbox range")
        records = tuple(program.records[start : start + capacity])
        result.append(
            SaturnMidi68KR24Batch(
                sequence=sequence,
                first_record_index=start,
                records=records,
            )
        )
    return tuple(result)


def _profile_polyphony(program: SaturnMidiProgram) -> _PolyphonyProfile:
    active: set[tuple[int, int]] = set()
    notes: list[int] = []
    peak = 0
    overlaps: list[int] = []

    for record in program.records:
        key = (record.channel, record.data0)
        before = len(active)
        if record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 != 0:
            active.add(key)
            notes.append(record.data0)
        elif record.opcode == SaturnMidiOpcode.NOTE_OFF or (
            record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1 == 0
        ):
            active.discard(key)

        current = len(active)
        if current > peak:
            peak = current
        if before < 2 and current == 2:
            overlaps.append(record.time_us)

    if active:
        raise SaturnMidi68KR24SongError(
            "R24 source leaves active notes at the end of the normalized program"
        )
    if not notes:
        raise SaturnMidi68KR24SongError("R24 source contains no Note On records")
    return _PolyphonyProfile(
        note_min=min(notes),
        note_max=max(notes),
        peak_polyphony=peak,
        overlap_times_us=tuple(overlaps),
    )


def build_saturn_midi_68k_r24_song_profile(
    source_path: os.PathLike[str] | str,
) -> SaturnMidi68KR24SongProfile:
    """Parse, schedule, compile, batch and profile one real Standard MIDI File."""

    source = Path(source_path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise SaturnMidi68KR24SongError(f"R24 MIDI source is not a file: {source}")

    midi = parse_midi_file(source)
    ticks_per_quarter = midi.header.ticks_per_quarter
    if ticks_per_quarter is None:
        raise SaturnMidi68KR24SongError("R24 first-song contract requires PPQN timing")

    tempo_map = build_midi_tempo_map(midi)
    if not tempo_map.points:
        raise SaturnMidi68KR24SongError("R24 MIDI tempo map is empty")
    if len(tempo_map.points) != 1:
        raise SaturnMidi68KR24SongError(
            "R24 first-song reference unexpectedly changed to a multi-tempo source"
        )

    program = compile_saturn_midi_program(midi)
    batches = batch_saturn_midi_r24_program(program)
    opcode_counts = Counter(record.opcode for record in program.records)
    polyphony = _profile_polyphony(program)

    return SaturnMidi68KR24SongProfile(
        source_path=source,
        source_sha256=_sha256_file(source),
        format_type=midi.header.format_type,
        track_count=midi.header.track_count,
        ticks_per_quarter=ticks_per_quarter,
        tempo_us_per_quarter=tempo_map.points[0].us_per_quarter,
        program=program,
        batches=batches,
        opcode_counts=tuple(sorted(opcode_counts.items(), key=lambda item: int(item[0]))),
        note_min=polyphony.note_min,
        note_max=polyphony.note_max,
        peak_polyphony=polyphony.peak_polyphony,
        overlap_times_us=polyphony.overlap_times_us,
    )


def validate_saturn_midi_68k_r24_reference_song(
    profile: SaturnMidi68KR24SongProfile,
) -> None:
    """Lock the exact CC0 file and semantics selected for the first real-song proof."""

    expected_counts = {
        SaturnMidiOpcode.NOTE_OFF: SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
        SaturnMidiOpcode.NOTE_ON: SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
        SaturnMidiOpcode.CONTROL_CHANGE: SATURN_MIDI_68K_R24_REFERENCE_CONTROL_CHANGE,
        SaturnMidiOpcode.PROGRAM_CHANGE: SATURN_MIDI_68K_R24_REFERENCE_PROGRAM_CHANGE,
        SaturnMidiOpcode.PITCH_BEND: SATURN_MIDI_68K_R24_REFERENCE_PITCH_BEND,
    }
    actual_counts = dict(profile.opcode_counts)

    checks = (
        (profile.source_sha256 == SATURN_MIDI_68K_R24_REFERENCE_SHA256, "source SHA-256"),
        (profile.format_type == SATURN_MIDI_68K_R24_REFERENCE_FORMAT, "SMF format"),
        (profile.track_count == SATURN_MIDI_68K_R24_REFERENCE_TRACKS, "track count"),
        (profile.ticks_per_quarter == SATURN_MIDI_68K_R24_REFERENCE_PPQN, "PPQN"),
        (
            profile.tempo_us_per_quarter == SATURN_MIDI_68K_R24_REFERENCE_TEMPO_US_PER_QUARTER,
            "tempo",
        ),
        (profile.record_count == SATURN_MIDI_68K_R24_REFERENCE_RECORDS, "record count"),
        (profile.duration_us == SATURN_MIDI_68K_R24_REFERENCE_DURATION_US, "duration"),
        (profile.note_min == SATURN_MIDI_68K_R24_REFERENCE_NOTE_MIN, "minimum note"),
        (profile.note_max == SATURN_MIDI_68K_R24_REFERENCE_NOTE_MAX, "maximum note"),
        (
            profile.peak_polyphony == SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
            "peak polyphony",
        ),
        (
            profile.overlap_times_us == SATURN_MIDI_68K_R24_REFERENCE_OVERLAP_TIMES_US,
            "two-note overlap points",
        ),
        (len(profile.batches) == SATURN_MIDI_68K_R24_REFERENCE_BATCHES, "batch count"),
        (
            profile.batches[-1].record_count == SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
            "last batch size",
        ),
    )
    for passed, label in checks:
        if not passed:
            raise SaturnMidi68KR24SongError(f"R24 reference-song {label} changed")

    if actual_counts != expected_counts:
        raise SaturnMidi68KR24SongError(
            f"R24 reference-song opcode counts changed: {actual_counts!r}"
        )
    if tuple(batch.record_count for batch in profile.batches) != (32,) * 9 + (22,):
        raise SaturnMidi68KR24SongError("R24 reference-song 32-record batching changed")
    if tuple(batch.sequence for batch in profile.batches) != tuple(range(1, 11)):
        raise SaturnMidi68KR24SongError("R24 reference-song sequence numbering changed")
