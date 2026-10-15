from hashlib import sha256
import json

import pytest

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
)
from rikai_kotoba.hardware.saturn.sbl_sequence import decode_uncompressed_saturn_m6
from rikai_kotoba.hardware.saturn.sbl_space_spectre_sequence import (
    BANK_NAME,
    EXPECTED_NOTE_COUNT,
    MANIFEST_NAME,
    SaturnSpaceSpectreSequenceError,
    build_space_spectre_native_sequence,
)


def test_full_space_spectre_compiles_to_one_song_native_sequence_bank(tmp_path):
    output = tmp_path / "space-spectre-native"
    result = build_space_spectre_native_sequence(output)

    assert result.source_sha256 == SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
    assert result.format_type == 1
    assert result.note_count == EXPECTED_NOTE_COUNT == 4381
    assert result.bank_path == output / BANK_NAME
    assert result.manifest_path == output / MANIFEST_NAME

    bank = result.bank_path.read_bytes()
    assert int.from_bytes(bank[0:2], "big") == 1
    assert int.from_bytes(bank[2:6], "big") == 6
    assert sha256(bank).hexdigest() == result.bank_sha256
    assert bank[6:] and sha256(bank[6:]).hexdigest() == result.song_sha256

    decoded = decode_uncompressed_saturn_m6(bank[6:])
    assert sum(event.kind == "note_on" for event in decoded) == 4381
    assert sum(event.kind == "end_of_track" for event in decoded) == 1

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "srk.saturn.sbl-space-spectre-sequence.v1"
    assert manifest["sequence_bank"]["song_count"] == 1
    assert manifest["sequence_bank"]["first_song_offset"] == 6
    assert manifest["policy"]["playback_path"] == "Sega SDDRV native sequence"
    assert manifest["policy"]["direct_midi_streaming"] is False
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
