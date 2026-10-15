from rikai_kotoba.formats.midi import MidiEvent, MidiFile, MidiHeader, MidiTrack
from rikai_kotoba.hardware.saturn.sbl_sequence import (
    SBL_AREA_SEQUENCE,
    SBL_AREA_TONE,
    SaturnSblArea,
    compile_midi_to_saturn_m6,
    decode_uncompressed_saturn_m6,
    encode_saturn_sequence_bank,
    encode_sbl_external_area_map,
)


def _space_spectre_shape_fixture() -> MidiFile:
    return MidiFile(
        header=MidiHeader(format_type=1, track_count=1, division=480),
        tracks=(
            MidiTrack(
                events=(
                    MidiEvent(0, 0, "set_tempo", 0xFF, meta_type=0x51, payload=b"\x07\xA1\x20"),
                    MidiEvent(0, 0, "program_change", 0xC0, channel=0, data=(30,)),
                    MidiEvent(0, 0, "note_on", 0x90, channel=0, data=(60, 100)),
                    MidiEvent(960, 960, "note_off", 0x80, channel=0, data=(60, 0)),
                    MidiEvent(0, 960, "end_of_track", 0xFF, meta_type=0x2F),
                )
            ),
        ),
    )


def test_external_area_map_matches_sega_mp_entry_shape():
    payload = encode_sbl_external_area_map(
        (
            SaturnSblArea(SBL_AREA_TONE, 0, 0x10000, 0x8000),
            SaturnSblArea(SBL_AREA_SEQUENCE, 0, 0x18000, 0x8000),
        )
    )
    assert payload == bytes.fromhex(
        "00 01 00 00 00 00 80 00 "
        "10 01 80 00 00 00 80 00 "
        "FF FF"
    )


def test_sequence_bank_is_count_offsets_then_song_payloads():
    payload = encode_saturn_sequence_bank((b"abc", b"defg"))
    assert payload[:2] == b"\x00\x02"
    assert int.from_bytes(payload[2:6], "big") == 10
    assert int.from_bytes(payload[6:10], "big") == 13
    assert payload[10:] == b"abcdefg"


def test_m6_conversion_folds_note_off_into_gate_and_preserves_long_time():
    converted = compile_midi_to_saturn_m6(_space_spectre_shape_fixture())
    assert converted.resolution == 480
    assert converted.tempo_event_count == 1
    assert converted.end_tick == 960
    assert converted.channel_event_count == 2
    assert converted.note_count == 1
    assert int.from_bytes(converted.song[2:4], "big") == 1
    assert int.from_bytes(converted.song[4:6], "big") == 16
    assert int.from_bytes(converted.song[8:12], "big") == 960
    assert int.from_bytes(converted.song[12:16], "big") == 500_000

    events = decode_uncompressed_saturn_m6(converted.song)
    assert [(event.kind, event.command, event.channel) for event in events] == [
        ("midi", 0xC0, 0),
        ("note_on", 0x90, 0),
        ("end_of_track", None, None),
    ]
    assert events[0].data0 == 30
    assert events[0].step_ticks == 0
    assert events[1].data0 == 60
    assert events[1].data1 == 100
    assert events[1].gate_ticks == 960
    assert events[1].step_ticks == 960


def test_sequence_bank_wraps_converted_song_at_sega_style_offset():
    converted = compile_midi_to_saturn_m6(_space_spectre_shape_fixture())
    bank = encode_saturn_sequence_bank((converted.song,))
    assert bank[:2] == b"\x00\x01"
    assert int.from_bytes(bank[2:6], "big") == 6
    assert bank[6:] == converted.song
