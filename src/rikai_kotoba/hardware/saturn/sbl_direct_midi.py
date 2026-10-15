"""Translate SRKM channel events into Sega Sound I/F Direct MIDI commands.

This module is deliberately a *musical backend boundary*, not another SCSP
voice synthesizer.  SRK keeps its already-validated MIDI parser and timestamped
SRKM schedule, while Sega's Saturn sound driver remains responsible for tone
bank interpretation, voice allocation and acoustic identity.

The mapping follows Sega's Sound I/F Library ``SND_CtrlDirMidi`` contract:

    SndRet SND_CtrlDirMidi(
        SndSeqNum seq_no,
        SndSeqPri seq_pri,
        Uint8 md_com,
        Uint8 ch,
        Uint8 dt1,
        Uint8 dt2
    );

SRKM v1 deliberately stores the seven MIDI channel-message classes in the same
order as Sega Direct MIDI, offset by one.  We still use an explicit mapping
below so that an enum edit cannot silently change the hardware contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from .midi_program import SaturnMidiOpcode, SaturnMidiProgram, SaturnMidiRecord


SBL_DIRECT_MIDI_SOUND_CONTROL_MIN = 0
SBL_DIRECT_MIDI_SOUND_CONTROL_MAX = 7
SBL_DIRECT_MIDI_PRIORITY_MIN = 0
SBL_DIRECT_MIDI_PRIORITY_MAX = 7
SBL_DIRECT_MIDI_CHANNEL_MIN = 0
SBL_DIRECT_MIDI_CHANNEL_MAX = 15
SBL_DIRECT_MIDI_DATA_MIN = 0
SBL_DIRECT_MIDI_DATA_MAX = 0x7F

# Sega's documented Direct MIDI command values for channel messages.
SBL_DIRECT_MIDI_NOTE_OFF = 0
SBL_DIRECT_MIDI_NOTE_ON = 1
SBL_DIRECT_MIDI_AFTER_TOUCH = 2
SBL_DIRECT_MIDI_CONTROL_CHANGE = 3
SBL_DIRECT_MIDI_PROGRAM_CHANGE = 4
SBL_DIRECT_MIDI_CHANNEL_PRESSURE = 5
SBL_DIRECT_MIDI_PITCH_WHEEL = 6
SBL_DIRECT_MIDI_SYSTEM_MESSAGE = 7

# SRKM v1 intentionally excludes System Message/SysEx, so only 0..6 are
# reachable through this adapter.
_SRKM_TO_SBL_DIRECT_MIDI = {
    SaturnMidiOpcode.NOTE_OFF: SBL_DIRECT_MIDI_NOTE_OFF,
    SaturnMidiOpcode.NOTE_ON: SBL_DIRECT_MIDI_NOTE_ON,
    SaturnMidiOpcode.POLY_AFTERTOUCH: SBL_DIRECT_MIDI_AFTER_TOUCH,
    SaturnMidiOpcode.CONTROL_CHANGE: SBL_DIRECT_MIDI_CONTROL_CHANGE,
    SaturnMidiOpcode.PROGRAM_CHANGE: SBL_DIRECT_MIDI_PROGRAM_CHANGE,
    SaturnMidiOpcode.CHANNEL_PRESSURE: SBL_DIRECT_MIDI_CHANNEL_PRESSURE,
    SaturnMidiOpcode.PITCH_BEND: SBL_DIRECT_MIDI_PITCH_WHEEL,
}


class SblDirectMidiError(RuntimeError):
    """Raised when an SRKM event cannot satisfy Sega Direct MIDI's contract."""


@dataclass(frozen=True)
class SblDirectMidiCommand:
    """One timestamped call-worth of arguments for ``SND_CtrlDirMidi``."""

    time_us: int
    seq_no: int
    seq_pri: int
    midi_command: int
    channel: int
    data1: int
    data2: int


def _require_range(value: int, minimum: int, maximum: int, label: str) -> int:
    if not isinstance(value, int):
        raise SblDirectMidiError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise SblDirectMidiError(
            f"{label} is outside {minimum}..{maximum}: {value}"
        )
    return value


def srkm_record_to_sbl_direct_midi(
    record: SaturnMidiRecord,
    *,
    seq_no: int = 2,
    seq_pri: int = 0,
) -> SblDirectMidiCommand:
    """Translate one SRKM v1 channel event without changing its MIDI meaning.

    ``data0`` and ``data1`` are forwarded byte-for-byte as Sega ``dt1`` and
    ``dt2``.  This is especially important for General MIDI percussion:
    channel 10 (zero-based channel 9 in SRKM) and its note numbers remain
    untouched.  Instrument/drum identity belongs to the loaded Sega tone bank,
    not to this adapter.
    """

    if not isinstance(record, SaturnMidiRecord):
        raise TypeError("record must be a SaturnMidiRecord")

    _require_range(
        seq_no,
        SBL_DIRECT_MIDI_SOUND_CONTROL_MIN,
        SBL_DIRECT_MIDI_SOUND_CONTROL_MAX,
        "Sega sound control number",
    )
    _require_range(
        seq_pri,
        SBL_DIRECT_MIDI_PRIORITY_MIN,
        SBL_DIRECT_MIDI_PRIORITY_MAX,
        "Sega Direct MIDI priority",
    )
    _require_range(
        record.channel,
        SBL_DIRECT_MIDI_CHANNEL_MIN,
        SBL_DIRECT_MIDI_CHANNEL_MAX,
        "MIDI channel",
    )
    _require_range(
        record.data0,
        SBL_DIRECT_MIDI_DATA_MIN,
        SBL_DIRECT_MIDI_DATA_MAX,
        "MIDI data1",
    )
    _require_range(
        record.data1,
        SBL_DIRECT_MIDI_DATA_MIN,
        SBL_DIRECT_MIDI_DATA_MAX,
        "MIDI data2",
    )
    if record.time_us < 0:
        raise SblDirectMidiError(f"MIDI event time cannot be negative: {record.time_us}")

    try:
        midi_command = _SRKM_TO_SBL_DIRECT_MIDI[record.opcode]
    except (KeyError, TypeError) as exc:
        raise SblDirectMidiError(
            f"SRKM opcode has no Sega Direct MIDI mapping: {record.opcode!r}"
        ) from exc

    return SblDirectMidiCommand(
        time_us=record.time_us,
        seq_no=seq_no,
        seq_pri=seq_pri,
        midi_command=midi_command,
        channel=record.channel,
        data1=record.data0,
        data2=record.data1,
    )


def srkm_program_to_sbl_direct_midi(
    program: SaturnMidiProgram,
    *,
    seq_no: int = 2,
    seq_pri: int = 0,
) -> tuple[SblDirectMidiCommand, ...]:
    """Translate a complete SRKM program while preserving schedule order/time."""

    if not isinstance(program, SaturnMidiProgram):
        raise TypeError("program must be a SaturnMidiProgram")
    return tuple(
        srkm_record_to_sbl_direct_midi(
            record,
            seq_no=seq_no,
            seq_pri=seq_pri,
        )
        for record in program.records
    )
