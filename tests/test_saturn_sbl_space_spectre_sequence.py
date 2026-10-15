from hashlib import sha256
import json

import pytest

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
)
from rikai_kotoba.hardware.saturn.sbl_sequence import decode_uncompressed_saturn_m6
from rikai_kotoba.hardware.saturn.sbl_space_spectre_sequence import (
    BANK_NAME,
    EXPECTED_BANK_BYTES,
    EXPECTED_BANK_SHA256,
    EXPECTED_CHANNEL_EVENT_COUNT,
    EXPECTED_NOTE_COUNT,
    EXPECTED_SONG_BYTES,
    EXPECTED_SONG_SHA256,
    EXPECTED_TONE_BANK_BINDINGS,
    MANIFEST_NAME,
    PERCUSSION_CHANNEL,
    PERCUSSION_PROGRAM,
    SaturnSpaceSpectreSequenceError,
    TONE_BANK_CONTROLLER,
    build_space_spectre_native_sequence,
)


def test_full_space_spectre_compiles_to_one_song_native_sequence_bank(tmp_path):
    output = tmp_path / "space-spectre-native"
    result = build_space_spectre_native_sequence(output)

    assert result.source_sha256 == SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
    assert result.format_type == 1
    assert result.note_count == EXPECTED_NOTE_COUNT == 4381
    assert result.channel_event_count == EXPECTED_CHANNEL_EVENT_COUNT == 4779
    assert result.tone_bank_bindings == EXPECTED_TONE_BANK_BINDINGS
    assert result.song_bytes == EXPECTED_SONG_BYTES == 23121
    assert result.song_sha256 == EXPECTED_SONG_SHA256
    assert result.bank_bytes == EXPECTED_BANK_BYTES == 23127
    assert result.bank_sha256 == EXPECTED_BANK_SHA256
    assert result.bank_path == output / BANK_NAME
    assert result.manifest_path == output / MANIFEST_NAME
    assert (PERCUSSION_CHANNEL, 1) in result.tone_bank_bindings
    assert all(bank in (0, 1) for _, bank in result.tone_bank_bindings)

    bank = result.bank_path.read_bytes()
    assert int.from_bytes(bank[0:2], "big") == 1
    assert int.from_bytes(bank[2:6], "big") == 6
    assert len(bank) == EXPECTED_BANK_BYTES
    assert sha256(bank).hexdigest() == EXPECTED_BANK_SHA256
    assert bank[6:] and sha256(bank[6:]).hexdigest() == EXPECTED_SONG_SHA256

    decoded = decode_uncompressed_saturn_m6(bank[6:])
    assert sum(event.kind == "note_on" for event in decoded) == 4381
    assert sum(event.kind == "end_of_track" for event in decoded) == 1

    bank_selects = {
        (event.channel, event.data1)
        for event in decoded
        if event.kind == "midi"
        and event.command == 0xB0
        and event.data0 == TONE_BANK_CONTROLLER
    }
    assert set(result.tone_bank_bindings).issubset(bank_selects)
    assert any(
        event.kind == "midi"
        and event.command == 0xC0
        and event.channel == PERCUSSION_CHANNEL
        and event.data0 == PERCUSSION_PROGRAM
        for event in decoded
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "srk.saturn.sbl-space-spectre-sequence.v2"
    assert manifest["sequence_bank"]["song_count"] == 1
    assert manifest["sequence_bank"]["first_song_offset"] == 6
    assert manifest["sequence_bank"]["bytes"] == EXPECTED_BANK_BYTES
    assert manifest["sequence_bank"]["sha256"] == EXPECTED_BANK_SHA256
    assert manifest["native_sequence"]["song_bytes"] == EXPECTED_SONG_BYTES
    assert manifest["native_sequence"]["song_sha256"] == EXPECTED_SONG_SHA256
    assert manifest["native_sequence"]["tone_bank_controller"] == 32
    assert {
        (item["channel_zero_based"], item["bank"])
        for item in manifest["native_sequence"]["tone_bank_bindings"]
    } == set(result.tone_bank_bindings)
    assert manifest["native_sequence"]["percussion_channel_zero_based"] == 9
    assert manifest["native_sequence"]["percussion_program"] == 0
    assert manifest["policy"]["playback_path"] == "Sega SDDRV native sequence"
    assert manifest["policy"]["direct_midi_streaming"] is False
    assert manifest["policy"]["sh2_midi_priming"] is False
    assert manifest["policy"]["saroo_writes"] is False
    assert manifest["policy"]["source_modified"] is False


def test_native_space_spectre_converter_refuses_overwrite(tmp_path):
    output = tmp_path / "already-there"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(SaturnSpaceSpectreSequenceError, match="refusing overwrite"):
        build_space_spectre_native_sequence(output)

    assert marker.read_text(encoding="utf-8") == "preserve"
