"""R26 Double Impact real-song profile and capacity model.

R26 consumes the exact CC0 Double Impact archive already stored in the SRK
repository. The source archive is reconstructed in memory from its five
lossless base64 transport chunks, hash-checked, and the selected Space Spectre
SMF is parsed directly from bytes. Source assets are never rewritten.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import io
from pathlib import Path
import zipfile

from rikai_kotoba.formats.midi import parse_midi_bytes
from .midi_68k_r24_song import batch_saturn_midi_r24_program
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, compile_saturn_midi_program


SATURN_MIDI_68K_R26_DOUBLE_IMPACT_PARTS = (
    "dbimmidi-oga-mid.zip.b64.000",
    "dbimmidi-oga-mid.zip.b64.001",
    "dbimmidi-oga-mid.zip.b64.002",
    "dbimmidi-oga-mid.zip.b64.003",
    "dbimmidi-oga-mid.zip.b64.004",
)
SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_BYTES = 45_337
SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_SHA256 = (
    "c665dd930726d25305f8c8e104a235399a04a04cf50d2f3eda251dd7be8d658c"
)
SATURN_MIDI_68K_R26_SPACE_SPECTRE_MEMBER = (
    "midis/E1M2, E4M3 - Matzu - Space Spectre.mid"
)
SATURN_MIDI_68K_R26_SPACE_SPECTRE_BYTES = 36_680
SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256 = (
    "984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01"
)
SATURN_MIDI_68K_R26_RELEASE_TAIL_US = 120_000
SATURN_MIDI_68K_R26_TARGET_SLOTS = 16
SATURN_MIDI_68K_R26_PERCUSSION_CHANNEL = 9


class SaturnMidi68KR26DoubleImpactError(RuntimeError):
    """Raised when the locked Double Impact source or R26 profile changes."""


@dataclass(frozen=True)
class SaturnMidi68KR26Capacity:
    slot_capacity: int
    peak_held: int
    peak_owned: int
    busy_count: int
    final_held: int
    final_releasing: int


@dataclass(frozen=True)
class SaturnMidi68KR26DoubleImpactProfile:
    archive_sha256: str
    member_name: str
    member_sha256: str
    format_type: int
    track_count: int
    ticks_per_quarter: int
    tempo_count: int
    record_count: int
    duration_us: int
    batch_count: int
    opcode_counts: tuple[tuple[SaturnMidiOpcode, int], ...]
    channels: tuple[int, ...]
    note_channels: tuple[int, ...]
    programs_by_channel: tuple[tuple[int, tuple[int, ...]], ...]
    controllers_by_channel: tuple[tuple[int, tuple[int, ...]], ...]
    percussion_notes: tuple[int, ...]
    sustain_event_count: int
    raw_peak_polyphony: int
    capacity: SaturnMidi68KR26Capacity
    program: SaturnMidiProgram

    @property
    def program_change_count(self) -> int:
        return dict(self.opcode_counts).get(SaturnMidiOpcode.PROGRAM_CHANGE, 0)

    @property
    def note_on_count(self) -> int:
        return dict(self.opcode_counts).get(SaturnMidiOpcode.NOTE_ON, 0)

    @property
    def note_off_count(self) -> int:
        return dict(self.opcode_counts).get(SaturnMidiOpcode.NOTE_OFF, 0)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _archive_directory(repository_root: Path | None = None) -> Path:
    base = _repo_root() if repository_root is None else Path(repository_root).resolve()
    return base / "assets" / "midi" / "cc0" / "double-impact"


def load_srk_saturn_midi_68k_r26_space_spectre_bytes(
    repository_root: Path | None = None,
) -> bytes:
    directory = _archive_directory(repository_root)
    encoded_parts = []
    for name in SATURN_MIDI_68K_R26_DOUBLE_IMPACT_PARTS:
        path = directory / name
        if not path.is_file():
            raise SaturnMidi68KR26DoubleImpactError(
                f"Double Impact transport part is missing: {path}"
            )
        encoded_parts.append(path.read_text(encoding="ascii"))
    try:
        archive_bytes = base64.b64decode("".join(encoded_parts), validate=True)
    except Exception as exc:
        raise SaturnMidi68KR26DoubleImpactError(
            "Double Impact base64 transport is invalid"
        ) from exc

    if len(archive_bytes) != SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_BYTES:
        raise SaturnMidi68KR26DoubleImpactError("Double Impact archive size changed")
    archive_sha = sha256(archive_bytes).hexdigest()
    if archive_sha != SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_SHA256:
        raise SaturnMidi68KR26DoubleImpactError("Double Impact archive SHA-256 changed")

    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            payload = archive.read(SATURN_MIDI_68K_R26_SPACE_SPECTRE_MEMBER)
    except (KeyError, zipfile.BadZipFile) as exc:
        raise SaturnMidi68KR26DoubleImpactError(
            "Space Spectre is missing from the locked Double Impact archive"
        ) from exc

    if len(payload) != SATURN_MIDI_68K_R26_SPACE_SPECTRE_BYTES:
        raise SaturnMidi68KR26DoubleImpactError("Space Spectre byte size changed")
    if sha256(payload).hexdigest() != SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256:
        raise SaturnMidi68KR26DoubleImpactError("Space Spectre SHA-256 changed")
    if payload[:4] != b"MThd":
        raise SaturnMidi68KR26DoubleImpactError("Space Spectre is not an SMF")
    return payload


def _raw_peak_polyphony(program: SaturnMidiProgram) -> int:
    active: set[tuple[int, int]] = set()
    peak = 0
    for record in program.records:
        key = (record.channel, record.data0)
        if record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1:
            active.add(key)
            peak = max(peak, len(active))
        elif record.opcode == SaturnMidiOpcode.NOTE_OFF:
            active.discard(key)
    return peak


def simulate_srk_saturn_midi_68k_r26_capacity(
    program: SaturnMidiProgram,
    *,
    slot_capacity: int = SATURN_MIDI_68K_R26_TARGET_SLOTS,
    release_tail_us: int = SATURN_MIDI_68K_R26_RELEASE_TAIL_US,
) -> SaturnMidi68KR26Capacity:
    if slot_capacity < 1 or slot_capacity > 32:
        raise SaturnMidi68KR26DoubleImpactError("R26 slot capacity must be within 1..32")
    if release_tail_us < 0:
        raise SaturnMidi68KR26DoubleImpactError("R26 release tail cannot be negative")

    slots = [[0, -1, -1, 0] for _ in range(slot_capacity)]
    peak_held = 0
    peak_owned = 0
    busy_count = 0

    def retire(now: int) -> None:
        for slot in slots:
            if slot[0] == 2 and slot[3] <= now:
                slot[:] = [0, -1, -1, 0]

    def counts() -> tuple[int, int]:
        held = sum(1 for slot in slots if slot[0] == 1)
        owned = sum(1 for slot in slots if slot[0] != 0)
        return held, owned

    for record in program.records:
        retire(record.time_us)
        if record.opcode == SaturnMidiOpcode.NOTE_ON and record.data1:
            match = next(
                (
                    slot
                    for slot in slots
                    if slot[0] != 0
                    and slot[1] == record.channel
                    and slot[2] == record.data0
                ),
                None,
            )
            target = match or next((slot for slot in slots if slot[0] == 0), None)
            if target is None:
                busy_count += 1
            else:
                target[:] = [1, record.channel, record.data0, 0]
        elif record.opcode == SaturnMidiOpcode.NOTE_OFF:
            target = next(
                (
                    slot
                    for slot in slots
                    if slot[0] == 1
                    and slot[1] == record.channel
                    and slot[2] == record.data0
                ),
                None,
            )
            if target is not None:
                target[0] = 2
                target[3] = record.time_us + release_tail_us

        held, owned = counts()
        peak_held = max(peak_held, held)
        peak_owned = max(peak_owned, owned)

    retire(program.duration_us + release_tail_us)
    final_held = sum(1 for slot in slots if slot[0] == 1)
    final_releasing = sum(1 for slot in slots if slot[0] == 2)
    return SaturnMidi68KR26Capacity(
        slot_capacity=slot_capacity,
        peak_held=peak_held,
        peak_owned=peak_owned,
        busy_count=busy_count,
        final_held=final_held,
        final_releasing=final_releasing,
    )


def build_srk_saturn_midi_68k_r26_space_spectre_profile(
    repository_root: Path | None = None,
    *,
    slot_capacity: int = SATURN_MIDI_68K_R26_TARGET_SLOTS,
) -> SaturnMidi68KR26DoubleImpactProfile:
    payload = load_srk_saturn_midi_68k_r26_space_spectre_bytes(repository_root)
    midi = parse_midi_bytes(payload)
    if midi.header.ticks_per_quarter is None:
        raise SaturnMidi68KR26DoubleImpactError(
            "Space Spectre uses SMPTE timing; R26 requires PPQN"
        )

    program = compile_saturn_midi_program(midi)
    batches = batch_saturn_midi_r24_program(program)
    opcode_counts = Counter(record.opcode for record in program.records)

    channels = sorted({record.channel for record in program.records})
    note_channels = sorted(
        {
            record.channel
            for record in program.records
            if record.opcode in (SaturnMidiOpcode.NOTE_ON, SaturnMidiOpcode.NOTE_OFF)
        }
    )
    programs: dict[int, set[int]] = defaultdict(set)
    controllers: dict[int, set[int]] = defaultdict(set)
    percussion_notes: set[int] = set()
    sustain_events = 0
    for record in program.records:
        if record.opcode == SaturnMidiOpcode.PROGRAM_CHANGE:
            programs[record.channel].add(record.data0)
        elif record.opcode == SaturnMidiOpcode.CONTROL_CHANGE:
            controllers[record.channel].add(record.data0)
            if record.data0 == 64:
                sustain_events += 1
        elif (
            record.opcode == SaturnMidiOpcode.NOTE_ON
            and record.data1
            and record.channel == SATURN_MIDI_68K_R26_PERCUSSION_CHANNEL
        ):
            percussion_notes.add(record.data0)

    tempo_count = sum(
        1
        for track in midi.tracks
        for event in track.events
        if event.kind == "set_tempo"
    )
    capacity = simulate_srk_saturn_midi_68k_r26_capacity(
        program, slot_capacity=slot_capacity
    )

    return SaturnMidi68KR26DoubleImpactProfile(
        archive_sha256=SATURN_MIDI_68K_R26_DOUBLE_IMPACT_ARCHIVE_SHA256,
        member_name=SATURN_MIDI_68K_R26_SPACE_SPECTRE_MEMBER,
        member_sha256=SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
        format_type=midi.header.format_type,
        track_count=midi.header.track_count,
        ticks_per_quarter=midi.header.ticks_per_quarter,
        tempo_count=tempo_count,
        record_count=len(program.records),
        duration_us=program.duration_us,
        batch_count=len(batches),
        opcode_counts=tuple(sorted(opcode_counts.items(), key=lambda item: int(item[0]))),
        channels=tuple(channels),
        note_channels=tuple(note_channels),
        programs_by_channel=tuple(
            (channel, tuple(sorted(values))) for channel, values in sorted(programs.items())
        ),
        controllers_by_channel=tuple(
            (channel, tuple(sorted(values)))
            for channel, values in sorted(controllers.items())
        ),
        percussion_notes=tuple(sorted(percussion_notes)),
        sustain_event_count=sustain_events,
        raw_peak_polyphony=_raw_peak_polyphony(program),
        capacity=capacity,
        program=program,
    )
