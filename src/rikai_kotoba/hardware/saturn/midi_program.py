"""Compile normalized MIDI schedules into a small Saturn playback contract.

The compiler deliberately stops before SCSP/MC68EC000 policy.  It turns the
platform-neutral scheduled MIDI events into deterministic, timestamped channel
commands that can be embedded in the standalone diagnostic, inspected by
Mjolnir, or consumed later by a sound-CPU mailbox implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import re

from rikai_kotoba.core.midi_sequence import build_midi_playback_schedule
from rikai_kotoba.formats.midi import MidiFile


SATURN_MIDI_PROGRAM_MAGIC = b"SRKM"
SATURN_MIDI_PROGRAM_VERSION = 1
SATURN_MIDI_PROGRAM_HEADER_BYTES = 16
SATURN_MIDI_PROGRAM_RECORD_BYTES = 8
SATURN_MIDI_PROGRAM_MAX_TIME_US = 0xFFFFFFFF


class SaturnMidiProgramError(RuntimeError):
    """Raised when a MIDI schedule cannot satisfy the Saturn program contract."""


class SaturnMidiOpcode(IntEnum):
    NOTE_OFF = 1
    NOTE_ON = 2
    POLY_AFTERTOUCH = 3
    CONTROL_CHANGE = 4
    PROGRAM_CHANGE = 5
    CHANNEL_PRESSURE = 6
    PITCH_BEND = 7


@dataclass(frozen=True)
class SaturnMidiRecord:
    time_us: int
    opcode: SaturnMidiOpcode
    channel: int
    data0: int
    data1: int


@dataclass(frozen=True)
class SaturnMidiProgram:
    records: tuple[SaturnMidiRecord, ...]
    duration_us: int

    def to_bytes(self) -> bytes:
        """Serialize the strict SRKM v1 big-endian playback program."""

        _validate_program(self)
        output = bytearray()
        output.extend(SATURN_MIDI_PROGRAM_MAGIC)
        output.append(SATURN_MIDI_PROGRAM_VERSION)
        output.append(SATURN_MIDI_PROGRAM_RECORD_BYTES)
        output.extend(b"\x00\x00")
        output.extend(len(self.records).to_bytes(4, "big"))
        output.extend(self.duration_us.to_bytes(4, "big"))
        for record in self.records:
            output.extend(record.time_us.to_bytes(4, "big"))
            output.extend(
                bytes(
                    (
                        int(record.opcode),
                        record.channel,
                        record.data0,
                        record.data1,
                    )
                )
            )
        return bytes(output)


def _require_data7(value: int, label: str) -> int:
    if value < 0 or value > 0x7F:
        raise SaturnMidiProgramError(f"{label} is outside MIDI 7-bit range: {value}")
    return value


def _record(
    time_us: int,
    opcode: SaturnMidiOpcode,
    channel: int,
    data0: int,
    data1: int = 0,
) -> SaturnMidiRecord:
    if time_us < 0 or time_us > SATURN_MIDI_PROGRAM_MAX_TIME_US:
        raise SaturnMidiProgramError(f"MIDI event time exceeds SRKM v1 range: {time_us}")
    if channel < 0 or channel > 15:
        raise SaturnMidiProgramError(f"MIDI channel out of range: {channel}")
    return SaturnMidiRecord(
        time_us=time_us,
        opcode=opcode,
        channel=channel,
        data0=_require_data7(data0, "MIDI data0"),
        data1=_require_data7(data1, "MIDI data1"),
    )


def _validate_program(program: SaturnMidiProgram) -> None:
    if not program.records:
        raise SaturnMidiProgramError("Saturn MIDI program contains no playable channel events")
    if program.duration_us < 0 or program.duration_us > SATURN_MIDI_PROGRAM_MAX_TIME_US:
        raise SaturnMidiProgramError(
            f"Saturn MIDI program duration exceeds SRKM v1 range: {program.duration_us}"
        )

    previous_time = -1
    for record in program.records:
        if record.time_us < previous_time:
            raise SaturnMidiProgramError("Saturn MIDI records are not in chronological order")
        previous_time = record.time_us
        if record.time_us > program.duration_us:
            raise SaturnMidiProgramError("Saturn MIDI record occurs after program duration")
        if not isinstance(record.opcode, SaturnMidiOpcode):
            raise SaturnMidiProgramError("Saturn MIDI record has an invalid opcode")
        if record.channel < 0 or record.channel > 15:
            raise SaturnMidiProgramError("Saturn MIDI record has an invalid channel")
        _require_data7(record.data0, "Saturn MIDI data0")
        _require_data7(record.data1, "Saturn MIDI data1")


def compile_saturn_midi_program(midi: MidiFile) -> SaturnMidiProgram:
    """Compile one format-0/1 PPQN MIDI timeline into deterministic SRKM v1."""

    schedule = build_midi_playback_schedule(midi)
    duration_us = max((item.time_us for item in schedule), default=0)
    if duration_us > SATURN_MIDI_PROGRAM_MAX_TIME_US:
        raise SaturnMidiProgramError(
            f"MIDI timeline exceeds SRKM v1 duration range: {duration_us}"
        )

    records: list[SaturnMidiRecord] = []
    for item in schedule:
        event = item.event
        if event.kind in ("sysex", "sysex_escape"):
            raise SaturnMidiProgramError(
                "SysEx is preserved by the MIDI parser but is not supported by SRKM v1"
            )
        if event.channel is None:
            continue

        channel = event.channel
        data = event.data
        if event.kind == "note_off" and len(data) == 2:
            records.append(_record(item.time_us, SaturnMidiOpcode.NOTE_OFF, channel, data[0], data[1]))
        elif event.kind == "note_on" and len(data) == 2:
            records.append(_record(item.time_us, SaturnMidiOpcode.NOTE_ON, channel, data[0], data[1]))
        elif event.kind == "poly_aftertouch" and len(data) == 2:
            records.append(
                _record(item.time_us, SaturnMidiOpcode.POLY_AFTERTOUCH, channel, data[0], data[1])
            )
        elif event.kind == "control_change" and len(data) == 2:
            records.append(
                _record(item.time_us, SaturnMidiOpcode.CONTROL_CHANGE, channel, data[0], data[1])
            )
        elif event.kind == "program_change" and len(data) == 1:
            records.append(_record(item.time_us, SaturnMidiOpcode.PROGRAM_CHANGE, channel, data[0]))
        elif event.kind == "channel_pressure" and len(data) == 1:
            records.append(_record(item.time_us, SaturnMidiOpcode.CHANNEL_PRESSURE, channel, data[0]))
        elif event.kind == "pitch_bend" and len(data) == 2:
            records.append(_record(item.time_us, SaturnMidiOpcode.PITCH_BEND, channel, data[0], data[1]))
        else:
            raise SaturnMidiProgramError(
                f"unsupported or malformed MIDI channel event for SRKM v1: {event.kind}"
            )

    program = SaturnMidiProgram(records=tuple(records), duration_us=duration_us)
    _validate_program(program)
    return program


def parse_saturn_midi_program_bytes(data: bytes) -> SaturnMidiProgram:
    """Strictly parse and validate one serialized SRKM v1 playback program."""

    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if len(data) < SATURN_MIDI_PROGRAM_HEADER_BYTES:
        raise SaturnMidiProgramError("SRKM payload is smaller than its header")
    if data[:4] != SATURN_MIDI_PROGRAM_MAGIC:
        raise SaturnMidiProgramError("SRKM magic mismatch")
    if data[4] != SATURN_MIDI_PROGRAM_VERSION:
        raise SaturnMidiProgramError(f"unsupported SRKM version: {data[4]}")
    if data[5] != SATURN_MIDI_PROGRAM_RECORD_BYTES:
        raise SaturnMidiProgramError(f"unsupported SRKM record size: {data[5]}")
    if data[6:8] != b"\x00\x00":
        raise SaturnMidiProgramError("SRKM reserved header bytes must be zero")

    record_count = int.from_bytes(data[8:12], "big")
    duration_us = int.from_bytes(data[12:16], "big")
    expected_size = SATURN_MIDI_PROGRAM_HEADER_BYTES + record_count * SATURN_MIDI_PROGRAM_RECORD_BYTES
    if len(data) != expected_size:
        raise SaturnMidiProgramError(
            f"SRKM size mismatch: expected {expected_size}, got {len(data)}"
        )

    records: list[SaturnMidiRecord] = []
    offset = SATURN_MIDI_PROGRAM_HEADER_BYTES
    for _ in range(record_count):
        time_us = int.from_bytes(data[offset : offset + 4], "big")
        opcode_value = data[offset + 4]
        try:
            opcode = SaturnMidiOpcode(opcode_value)
        except ValueError as exc:
            raise SaturnMidiProgramError(f"unknown SRKM opcode: {opcode_value}") from exc
        records.append(
            SaturnMidiRecord(
                time_us=time_us,
                opcode=opcode,
                channel=data[offset + 5],
                data0=data[offset + 6],
                data1=data[offset + 7],
            )
        )
        offset += SATURN_MIDI_PROGRAM_RECORD_BYTES

    program = SaturnMidiProgram(records=tuple(records), duration_us=duration_us)
    _validate_program(program)
    return program


_C_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def render_saturn_midi_program_c(
    program: SaturnMidiProgram,
    *,
    symbol_prefix: str = "srk_midi_diag",
) -> str:
    """Render one SRKM program as C89-compatible constant playback records."""

    _validate_program(program)
    if _C_SYMBOL_RE.fullmatch(symbol_prefix) is None:
        raise SaturnMidiProgramError(f"invalid C symbol prefix: {symbol_prefix!r}")

    lines = [
        "/* Generated by SRK from a deterministic normalized MIDI schedule. */",
        "typedef struct SRK_MIDI_PROGRAM_EVENT {",
        "    unsigned long time_us;",
        "    unsigned char opcode;",
        "    unsigned char channel;",
        "    unsigned char data0;",
        "    unsigned char data1;",
        "} SRK_MIDI_PROGRAM_EVENT;",
        "",
        f"static const SRK_MIDI_PROGRAM_EVENT {symbol_prefix}_events[] = {{",
    ]
    for record in program.records:
        lines.append(
            "    {%dUL, %du, %du, %du, %du},"
            % (
                record.time_us,
                int(record.opcode),
                record.channel,
                record.data0,
                record.data1,
            )
        )
    lines.extend(
        (
            "};",
            "",
            f"static const unsigned long {symbol_prefix}_event_count = {len(program.records)}UL;",
            f"static const unsigned long {symbol_prefix}_duration_us = {program.duration_us}UL;",
            "",
        )
    )
    return "\n".join(lines)
