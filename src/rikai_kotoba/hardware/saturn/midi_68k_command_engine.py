"""Silent multi-record MIDI command/state model for the Saturn MC68EC000 driver.

R18 physically proved the SH-2 -> Sound RAM -> resident MC68EC000 -> mailbox
round trip.  This module deliberately moves one layer forward without touching
SCSP registers: it defines the bounded Sound-RAM state contract and the exact
state transitions that the next resident 68K image must implement.

The model consumes SRKM v1 channel records, tracks all 128 controller values,
logical note velocities and the channel-level state needed by later voice
allocation.  It acknowledges the complete bounded queue only after every record
has been validated and consumed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .midi_bridge import (
    SATURN_MIDI_QUEUE_ADDRESS,
    SATURN_MIDI_QUEUE_BYTES,
    SATURN_MIDI_QUEUE_CAPACITY,
)
from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SATURN_MIDI_68K_CHANNEL_COUNT = 16
SATURN_MIDI_68K_CONTROLLER_COUNT = 128
SATURN_MIDI_68K_NOTE_COUNT = 128

# The queue ends at 0x1200.  Keep every new silent-driver state byte below the
# established standalone Audio/SCSP ownership beginning at 0x2000.
SATURN_MIDI_68K_STATE_ADDRESS = SATURN_MIDI_QUEUE_ADDRESS + SATURN_MIDI_QUEUE_BYTES
SATURN_MIDI_68K_CHANNEL_STATE_WORDS = 16
SATURN_MIDI_68K_CHANNEL_STATE_BYTES = SATURN_MIDI_68K_CHANNEL_STATE_WORDS * 2
SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES = (
    SATURN_MIDI_68K_CHANNEL_COUNT * SATURN_MIDI_68K_CHANNEL_STATE_BYTES
)
SATURN_MIDI_68K_CONTROLLER_ADDRESS = 0x00001400
SATURN_MIDI_68K_CONTROLLER_BYTES = (
    SATURN_MIDI_68K_CHANNEL_COUNT * SATURN_MIDI_68K_CONTROLLER_COUNT
)
SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS = 0x00001C00
SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL = SATURN_MIDI_68K_NOTE_COUNT // 8
SATURN_MIDI_68K_ACTIVE_NOTES_BYTES = (
    SATURN_MIDI_68K_CHANNEL_COUNT * SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL
)
SATURN_MIDI_68K_TELEMETRY_ADDRESS = 0x00001D00
SATURN_MIDI_68K_TELEMETRY_BYTES = 0x00000100
SATURN_MIDI_68K_STATE_END = SATURN_MIDI_68K_TELEMETRY_ADDRESS + SATURN_MIDI_68K_TELEMETRY_BYTES
SATURN_MIDI_68K_AUDIO_BOUNDARY = 0x00002000

SATURN_MIDI_68K_CH_PROGRAM = 0
SATURN_MIDI_68K_CH_BANK_MSB = 1
SATURN_MIDI_68K_CH_BANK_LSB = 2
SATURN_MIDI_68K_CH_VOLUME = 3
SATURN_MIDI_68K_CH_PAN = 4
SATURN_MIDI_68K_CH_EXPRESSION = 5
SATURN_MIDI_68K_CH_SUSTAIN = 6
SATURN_MIDI_68K_CH_CHANNEL_PRESSURE = 7
SATURN_MIDI_68K_CH_PITCH_BEND = 8
SATURN_MIDI_68K_CH_LAST_NOTE = 9
SATURN_MIDI_68K_CH_LAST_VELOCITY = 10
SATURN_MIDI_68K_CH_LAST_POLY_NOTE = 11
SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE = 12
SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT = 13
SATURN_MIDI_68K_CH_EVENT_COUNT = 14
SATURN_MIDI_68K_CH_LAST_OPCODE = 15
SATURN_MIDI_68K_NO_NOTE = 0xFFFF

SATURN_MIDI_68K_DEFAULT_VOLUME = 100
SATURN_MIDI_68K_DEFAULT_PAN = 64
SATURN_MIDI_68K_DEFAULT_EXPRESSION = 127
SATURN_MIDI_68K_DEFAULT_PITCH_BEND = 0x2000


class SaturnMidi68KCommandEngineError(RuntimeError):
    """Raised when a silent 68K command batch violates the reviewed contract."""


@dataclass(frozen=True)
class SaturnMidi68KChannelState:
    program: int
    bank_msb: int
    bank_lsb: int
    volume: int
    pan: int
    expression: int
    sustain: int
    channel_pressure: int
    pitch_bend: int
    last_note: int
    last_velocity: int
    last_poly_note: int
    last_poly_pressure: int
    event_count: int
    last_opcode: int
    controllers: tuple[int, ...]
    note_velocities: tuple[int, ...]

    @property
    def active_notes(self) -> tuple[int, ...]:
        return tuple(index for index, velocity in enumerate(self.note_velocities) if velocity)

    @property
    def active_note_count(self) -> int:
        return len(self.active_notes)


@dataclass(frozen=True)
class SaturnMidi68KSilentEngineResult:
    channels: tuple[SaturnMidi68KChannelState, ...]
    processed_records: int
    read_index: int
    read_sequence: int
    last_error: int
    final_time_us: int


def _default_controllers() -> tuple[int, ...]:
    values = [0] * SATURN_MIDI_68K_CONTROLLER_COUNT
    values[7] = SATURN_MIDI_68K_DEFAULT_VOLUME
    values[10] = SATURN_MIDI_68K_DEFAULT_PAN
    values[11] = SATURN_MIDI_68K_DEFAULT_EXPRESSION
    return tuple(values)


def default_saturn_midi_68k_channel_state() -> SaturnMidi68KChannelState:
    """Return one deterministic SRK driver channel reset state."""

    return SaturnMidi68KChannelState(
        program=0,
        bank_msb=0,
        bank_lsb=0,
        volume=SATURN_MIDI_68K_DEFAULT_VOLUME,
        pan=SATURN_MIDI_68K_DEFAULT_PAN,
        expression=SATURN_MIDI_68K_DEFAULT_EXPRESSION,
        sustain=0,
        channel_pressure=0,
        pitch_bend=SATURN_MIDI_68K_DEFAULT_PITCH_BEND,
        last_note=SATURN_MIDI_68K_NO_NOTE,
        last_velocity=0,
        last_poly_note=SATURN_MIDI_68K_NO_NOTE,
        last_poly_pressure=0,
        event_count=0,
        last_opcode=0,
        controllers=_default_controllers(),
        note_velocities=(0,) * SATURN_MIDI_68K_NOTE_COUNT,
    )


def validate_srk_saturn_midi_68k_command_layout() -> None:
    """Prove the new silent state fits between the queue and Audio/SCSP RAM."""

    if SATURN_MIDI_68K_STATE_ADDRESS != 0x00001200:
        raise SaturnMidi68KCommandEngineError("silent state no longer begins at queue end")
    if (
        SATURN_MIDI_68K_STATE_ADDRESS + SATURN_MIDI_68K_CHANNEL_STATE_TOTAL_BYTES
        > SATURN_MIDI_68K_CONTROLLER_ADDRESS
    ):
        raise SaturnMidi68KCommandEngineError("channel summary overlaps controller state")
    if SATURN_MIDI_68K_CONTROLLER_ADDRESS + SATURN_MIDI_68K_CONTROLLER_BYTES > SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS:
        raise SaturnMidi68KCommandEngineError("controller state overlaps active-note bitmap")
    if SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS + SATURN_MIDI_68K_ACTIVE_NOTES_BYTES > SATURN_MIDI_68K_TELEMETRY_ADDRESS:
        raise SaturnMidi68KCommandEngineError("active-note bitmap overlaps telemetry")
    if SATURN_MIDI_68K_STATE_END > SATURN_MIDI_68K_AUDIO_BOUNDARY:
        raise SaturnMidi68KCommandEngineError("silent MIDI state overlaps accepted Audio/SCSP ownership")


def _require_data7(value: int, label: str) -> int:
    if value < 0 or value > 0x7F:
        raise SaturnMidi68KCommandEngineError(f"{label} is outside MIDI 7-bit range: {value}")
    return value


def _validate_record(record: SaturnMidiRecord, previous_time: int) -> None:
    if record.time_us < previous_time:
        raise SaturnMidi68KCommandEngineError("silent MIDI queue is not chronological")
    if not isinstance(record.opcode, SaturnMidiOpcode):
        raise SaturnMidi68KCommandEngineError("silent MIDI queue contains an invalid opcode")
    if record.channel < 0 or record.channel >= SATURN_MIDI_68K_CHANNEL_COUNT:
        raise SaturnMidi68KCommandEngineError("silent MIDI queue contains an invalid channel")
    _require_data7(record.data0, "MIDI data0")
    _require_data7(record.data1, "MIDI data1")


def _consume_record(
    state: SaturnMidi68KChannelState,
    record: SaturnMidiRecord,
) -> SaturnMidi68KChannelState:
    controllers = list(state.controllers)
    notes = list(state.note_velocities)
    updates: dict[str, int | tuple[int, ...]] = {
        "event_count": state.event_count + 1,
        "last_opcode": int(record.opcode),
    }

    if record.opcode == SaturnMidiOpcode.NOTE_OFF:
        notes[record.data0] = 0
        updates["last_note"] = record.data0
        updates["last_velocity"] = record.data1
    elif record.opcode == SaturnMidiOpcode.NOTE_ON:
        notes[record.data0] = record.data1
        updates["last_note"] = record.data0
        updates["last_velocity"] = record.data1
    elif record.opcode == SaturnMidiOpcode.POLY_AFTERTOUCH:
        updates["last_poly_note"] = record.data0
        updates["last_poly_pressure"] = record.data1
    elif record.opcode == SaturnMidiOpcode.CONTROL_CHANGE:
        controllers[record.data0] = record.data1
        if record.data0 == 0:
            updates["bank_msb"] = record.data1
        elif record.data0 == 32:
            updates["bank_lsb"] = record.data1
        elif record.data0 == 7:
            updates["volume"] = record.data1
        elif record.data0 == 10:
            updates["pan"] = record.data1
        elif record.data0 == 11:
            updates["expression"] = record.data1
        elif record.data0 == 64:
            updates["sustain"] = 1 if record.data1 >= 64 else 0
    elif record.opcode == SaturnMidiOpcode.PROGRAM_CHANGE:
        updates["program"] = record.data0
    elif record.opcode == SaturnMidiOpcode.CHANNEL_PRESSURE:
        updates["channel_pressure"] = record.data0
    elif record.opcode == SaturnMidiOpcode.PITCH_BEND:
        updates["pitch_bend"] = (record.data1 << 7) | record.data0
    else:  # pragma: no cover - enum validation above makes this defensive only.
        raise SaturnMidi68KCommandEngineError(f"unhandled SRKM opcode: {record.opcode}")

    updates["controllers"] = tuple(controllers)
    updates["note_velocities"] = tuple(notes)
    return replace(state, **updates)


def simulate_srk_saturn_midi_68k_command_engine(
    program: SaturnMidiProgram,
    *,
    write_sequence: int = 1,
) -> SaturnMidi68KSilentEngineResult:
    """Consume one bounded SRKM batch without touching SCSP or other hardware."""

    validate_srk_saturn_midi_68k_command_layout()
    if write_sequence < 1 or write_sequence > 0xFFFF:
        raise SaturnMidi68KCommandEngineError("write sequence must fit non-zero 16-bit mailbox state")
    if not program.records:
        raise SaturnMidi68KCommandEngineError("silent MIDI engine requires at least one record")
    if len(program.records) > SATURN_MIDI_QUEUE_CAPACITY:
        raise SaturnMidi68KCommandEngineError("silent MIDI batch exceeds the bounded Sound-RAM queue")

    channels = [default_saturn_midi_68k_channel_state() for _ in range(SATURN_MIDI_68K_CHANNEL_COUNT)]
    previous_time = -1
    for record in program.records:
        _validate_record(record, previous_time)
        previous_time = record.time_us
        channels[record.channel] = _consume_record(channels[record.channel], record)

    return SaturnMidi68KSilentEngineResult(
        channels=tuple(channels),
        processed_records=len(program.records),
        read_index=len(program.records),
        read_sequence=write_sequence,
        last_error=0,
        final_time_us=program.records[-1].time_us,
    )


def pack_srk_saturn_midi_68k_channel_words(
    state: SaturnMidi68KChannelState,
) -> tuple[int, ...]:
    """Pack one channel summary into the reviewed 16-word Sound-RAM contract."""

    words = (
        state.program,
        state.bank_msb,
        state.bank_lsb,
        state.volume,
        state.pan,
        state.expression,
        state.sustain,
        state.channel_pressure,
        state.pitch_bend,
        state.last_note,
        state.last_velocity,
        state.last_poly_note,
        state.last_poly_pressure,
        state.active_note_count,
        state.event_count,
        state.last_opcode,
    )
    if len(words) != SATURN_MIDI_68K_CHANNEL_STATE_WORDS:
        raise SaturnMidi68KCommandEngineError("channel summary word count changed unexpectedly")
    if any(value < 0 or value > 0xFFFF for value in words):
        raise SaturnMidi68KCommandEngineError("channel summary value exceeds 16-bit Sound-RAM word")
    return words


def pack_srk_saturn_midi_68k_state_words(
    result: SaturnMidi68KSilentEngineResult,
) -> tuple[int, ...]:
    """Pack all sixteen channel summaries in channel-major order."""

    if len(result.channels) != SATURN_MIDI_68K_CHANNEL_COUNT:
        raise SaturnMidi68KCommandEngineError("silent MIDI result must contain sixteen channels")
    return tuple(
        word
        for channel in result.channels
        for word in pack_srk_saturn_midi_68k_channel_words(channel)
    )


def pack_srk_saturn_midi_68k_controller_bytes(
    result: SaturnMidi68KSilentEngineResult,
) -> bytes:
    """Pack all 128 CC values per channel in channel-major order."""

    payload = bytes(value for channel in result.channels for value in channel.controllers)
    if len(payload) != SATURN_MIDI_68K_CONTROLLER_BYTES:
        raise SaturnMidi68KCommandEngineError("controller-state byte count changed unexpectedly")
    return payload


def pack_srk_saturn_midi_68k_active_note_bitmap(
    result: SaturnMidi68KSilentEngineResult,
) -> bytes:
    """Pack one 128-note logical-key bitmap per channel, low note in low bit."""

    payload = bytearray()
    for channel in result.channels:
        bitmap = bytearray(SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL)
        for note, velocity in enumerate(channel.note_velocities):
            if velocity:
                bitmap[note >> 3] |= 1 << (note & 7)
        payload.extend(bitmap)
    if len(payload) != SATURN_MIDI_68K_ACTIVE_NOTES_BYTES:
        raise SaturnMidi68KCommandEngineError("active-note bitmap size changed unexpectedly")
    return bytes(payload)


def render_srk_saturn_midi_68k_command_state_header() -> str:
    """Render the inert C89-visible Sound-RAM state contract for later 68K code."""

    constants = (
        ("SRK_MIDI_68K_STATE_ADDRESS", SATURN_MIDI_68K_STATE_ADDRESS, "UL"),
        ("SRK_MIDI_68K_CHANNEL_COUNT", SATURN_MIDI_68K_CHANNEL_COUNT, "u"),
        ("SRK_MIDI_68K_CHANNEL_STATE_WORDS", SATURN_MIDI_68K_CHANNEL_STATE_WORDS, "u"),
        ("SRK_MIDI_68K_CHANNEL_STATE_BYTES", SATURN_MIDI_68K_CHANNEL_STATE_BYTES, "u"),
        ("SRK_MIDI_68K_CONTROLLER_ADDRESS", SATURN_MIDI_68K_CONTROLLER_ADDRESS, "UL"),
        ("SRK_MIDI_68K_CONTROLLER_COUNT", SATURN_MIDI_68K_CONTROLLER_COUNT, "u"),
        ("SRK_MIDI_68K_ACTIVE_NOTES_ADDRESS", SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, "UL"),
        ("SRK_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL", SATURN_MIDI_68K_ACTIVE_NOTE_BYTES_PER_CHANNEL, "u"),
        ("SRK_MIDI_68K_TELEMETRY_ADDRESS", SATURN_MIDI_68K_TELEMETRY_ADDRESS, "UL"),
        ("SRK_MIDI_68K_TELEMETRY_BYTES", SATURN_MIDI_68K_TELEMETRY_BYTES, "u"),
    )
    lines = [
        "#ifndef SRK_SATURN_MIDI_68K_COMMAND_STATE_H",
        "#define SRK_SATURN_MIDI_68K_COMMAND_STATE_H",
        "",
        "/* Silent command/state contract only. No SCSP voice writes are enabled. */",
    ]
    for name, value, suffix in constants:
        if suffix == "UL":
            lines.append(f"#define {name} 0x{value:08X}{suffix}")
        else:
            lines.append(f"#define {name} {value}{suffix}")
    lines.extend(
        (
            "",
            f"#define SRK_MIDI_68K_CH_PROGRAM {SATURN_MIDI_68K_CH_PROGRAM}u",
            f"#define SRK_MIDI_68K_CH_BANK_MSB {SATURN_MIDI_68K_CH_BANK_MSB}u",
            f"#define SRK_MIDI_68K_CH_BANK_LSB {SATURN_MIDI_68K_CH_BANK_LSB}u",
            f"#define SRK_MIDI_68K_CH_VOLUME {SATURN_MIDI_68K_CH_VOLUME}u",
            f"#define SRK_MIDI_68K_CH_PAN {SATURN_MIDI_68K_CH_PAN}u",
            f"#define SRK_MIDI_68K_CH_EXPRESSION {SATURN_MIDI_68K_CH_EXPRESSION}u",
            f"#define SRK_MIDI_68K_CH_SUSTAIN {SATURN_MIDI_68K_CH_SUSTAIN}u",
            f"#define SRK_MIDI_68K_CH_CHANNEL_PRESSURE {SATURN_MIDI_68K_CH_CHANNEL_PRESSURE}u",
            f"#define SRK_MIDI_68K_CH_PITCH_BEND {SATURN_MIDI_68K_CH_PITCH_BEND}u",
            f"#define SRK_MIDI_68K_CH_LAST_NOTE {SATURN_MIDI_68K_CH_LAST_NOTE}u",
            f"#define SRK_MIDI_68K_CH_LAST_VELOCITY {SATURN_MIDI_68K_CH_LAST_VELOCITY}u",
            f"#define SRK_MIDI_68K_CH_LAST_POLY_NOTE {SATURN_MIDI_68K_CH_LAST_POLY_NOTE}u",
            f"#define SRK_MIDI_68K_CH_LAST_POLY_PRESSURE {SATURN_MIDI_68K_CH_LAST_POLY_PRESSURE}u",
            f"#define SRK_MIDI_68K_CH_ACTIVE_NOTE_COUNT {SATURN_MIDI_68K_CH_ACTIVE_NOTE_COUNT}u",
            f"#define SRK_MIDI_68K_CH_EVENT_COUNT {SATURN_MIDI_68K_CH_EVENT_COUNT}u",
            f"#define SRK_MIDI_68K_CH_LAST_OPCODE {SATURN_MIDI_68K_CH_LAST_OPCODE}u",
            f"#define SRK_MIDI_68K_NO_NOTE 0x{SATURN_MIDI_68K_NO_NOTE:04X}u",
            "",
            "#endif",
            "",
        )
    )
    return "\n".join(lines)
