from __future__ import annotations

from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_PERCUSSION_CHANNEL,
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)
from rikai_kotoba.hardware.saturn.sbl_direct_midi import (
    SBL_DIRECT_MIDI_AFTER_TOUCH,
    SBL_DIRECT_MIDI_CHANNEL_PRESSURE,
    SBL_DIRECT_MIDI_CONTROL_CHANGE,
    SBL_DIRECT_MIDI_NOTE_OFF,
    SBL_DIRECT_MIDI_NOTE_ON,
    SBL_DIRECT_MIDI_PITCH_WHEEL,
    SBL_DIRECT_MIDI_PROGRAM_CHANGE,
    SblDirectMidiError,
    srkm_program_to_sbl_direct_midi,
    srkm_record_to_sbl_direct_midi,
)


_ROOT = Path(__file__).resolve().parents[1]


def _record(
    opcode: SaturnMidiOpcode,
    *,
    channel: int = 3,
    data0: int = 64,
    data1: int = 96,
) -> SaturnMidiRecord:
    return SaturnMidiRecord(
        time_us=123456,
        opcode=opcode,
        channel=channel,
        data0=data0,
        data1=data1,
    )


def test_all_srkm_channel_opcodes_map_exactly_to_sega_direct_midi():
    expected = (
        (SaturnMidiOpcode.NOTE_OFF, SBL_DIRECT_MIDI_NOTE_OFF),
        (SaturnMidiOpcode.NOTE_ON, SBL_DIRECT_MIDI_NOTE_ON),
        (SaturnMidiOpcode.POLY_AFTERTOUCH, SBL_DIRECT_MIDI_AFTER_TOUCH),
        (SaturnMidiOpcode.CONTROL_CHANGE, SBL_DIRECT_MIDI_CONTROL_CHANGE),
        (SaturnMidiOpcode.PROGRAM_CHANGE, SBL_DIRECT_MIDI_PROGRAM_CHANGE),
        (SaturnMidiOpcode.CHANNEL_PRESSURE, SBL_DIRECT_MIDI_CHANNEL_PRESSURE),
        (SaturnMidiOpcode.PITCH_BEND, SBL_DIRECT_MIDI_PITCH_WHEEL),
    )

    for opcode, sega_command in expected:
        command = srkm_record_to_sbl_direct_midi(_record(opcode), seq_no=2, seq_pri=0)
        assert command.time_us == 123456
        assert command.seq_no == 2
        assert command.seq_pri == 0
        assert command.midi_command == sega_command
        assert command.channel == 3
        assert command.data1 == 64
        assert command.data2 == 96


def test_program_change_and_pitch_bend_keep_original_midi_data_bytes():
    program_change = srkm_record_to_sbl_direct_midi(
        _record(SaturnMidiOpcode.PROGRAM_CHANGE, channel=1, data0=39, data1=0)
    )
    assert program_change.midi_command == SBL_DIRECT_MIDI_PROGRAM_CHANGE
    assert (program_change.channel, program_change.data1, program_change.data2) == (1, 39, 0)

    pitch_bend = srkm_record_to_sbl_direct_midi(
        _record(SaturnMidiOpcode.PITCH_BEND, channel=2, data0=0x21, data1=0x52)
    )
    assert pitch_bend.midi_command == SBL_DIRECT_MIDI_PITCH_WHEEL
    assert (pitch_bend.channel, pitch_bend.data1, pitch_bend.data2) == (2, 0x21, 0x52)


def test_space_spectre_percussion_is_forwarded_as_real_midi_drum_notes():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    commands = srkm_program_to_sbl_direct_midi(profile.program)

    assert len(commands) == 9154
    assert len(commands) == len(profile.program.records)

    percussion_note_ons = {
        command.data1
        for command in commands
        if command.channel == SATURN_MIDI_68K_R26_PERCUSSION_CHANNEL
        and command.midi_command == SBL_DIRECT_MIDI_NOTE_ON
        and command.data2 != 0
    }
    assert percussion_note_ons == {35, 40, 42, 51}

    # The adapter must never re-pitch, collapse, substitute or synthesize the
    # drum kit.  It forwards channel 10 (zero-based 9) and the MIDI note number
    # exactly; Sega's loaded tone bank decides which drum sample sounds.
    for record, command in zip(profile.program.records, commands, strict=True):
        assert command.time_us == record.time_us
        assert command.channel == record.channel
        assert command.data1 == record.data0
        assert command.data2 == record.data1


def test_complete_program_translation_preserves_order_and_timestamps():
    program = SaturnMidiProgram(
        records=(
            _record(SaturnMidiOpcode.NOTE_ON, channel=0, data0=60, data1=127),
            SaturnMidiRecord(
                time_us=223456,
                opcode=SaturnMidiOpcode.NOTE_OFF,
                channel=0,
                data0=60,
                data1=64,
            ),
        ),
        duration_us=223456,
    )
    commands = srkm_program_to_sbl_direct_midi(program, seq_no=7, seq_pri=0)

    assert [command.time_us for command in commands] == [123456, 223456]
    assert [command.midi_command for command in commands] == [
        SBL_DIRECT_MIDI_NOTE_ON,
        SBL_DIRECT_MIDI_NOTE_OFF,
    ]
    assert all(command.seq_no == 7 for command in commands)


def test_direct_midi_contract_rejects_out_of_range_values():
    with pytest.raises(SblDirectMidiError, match="sound control"):
        srkm_record_to_sbl_direct_midi(_record(SaturnMidiOpcode.NOTE_ON), seq_no=8)
    with pytest.raises(SblDirectMidiError, match="priority"):
        srkm_record_to_sbl_direct_midi(_record(SaturnMidiOpcode.NOTE_ON), seq_pri=8)
    with pytest.raises(SblDirectMidiError, match="channel"):
        srkm_record_to_sbl_direct_midi(
            _record(SaturnMidiOpcode.NOTE_ON, channel=16)
        )
    with pytest.raises(SblDirectMidiError, match="data1"):
        srkm_record_to_sbl_direct_midi(
            _record(SaturnMidiOpcode.NOTE_ON, data0=128)
        )
    with pytest.raises(SblDirectMidiError, match="data2"):
        srkm_record_to_sbl_direct_midi(
            _record(SaturnMidiOpcode.NOTE_ON, data1=128)
        )


def test_direct_midi_contract_rejects_unknown_srkm_opcode_and_negative_time():
    unknown = SaturnMidiRecord(
        time_us=0,
        opcode=99,  # type: ignore[arg-type]
        channel=0,
        data0=0,
        data1=0,
    )
    with pytest.raises(SblDirectMidiError, match="no Sega Direct MIDI mapping"):
        srkm_record_to_sbl_direct_midi(unknown)

    negative = SaturnMidiRecord(
        time_us=-1,
        opcode=SaturnMidiOpcode.NOTE_ON,
        channel=0,
        data0=60,
        data1=127,
    )
    with pytest.raises(SblDirectMidiError, match="negative"):
        srkm_record_to_sbl_direct_midi(negative)
