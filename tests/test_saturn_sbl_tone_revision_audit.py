from dataclasses import replace
from pathlib import Path
import struct

from rikai_kotoba.hardware.saturn.sbl_soundfont_channel10 import (
    SEGA_BOOTTONE_VELOCITY_CURVE_0,
    normalize_sega_velocity_curve_bytes,
)
from rikai_kotoba.hardware.saturn.sbl_tone_revision_audit import (
    GATE3E_DRUM_SHA256,
    GATE3E_MELODIC_SHA256,
    SaturnTonePolicyModel,
    SaturnToneSemanticRow,
    _changed_rows,
)
from rikai_kotoba.tools.saturn_sbl_tone_revision_audit import build_parser


def _row() -> SaturnToneSemanticRow:
    return SaturnToneSemanticRow(
        kind="melodic",
        program=30,
        note=60,
        velocity=100,
        preset_bank=0,
        preset_name="test",
        sample_id=1,
        sample_name="sample",
        source_rate=44100,
        source_root=60,
        pitch_correction=0,
        zone_root=None,
        zone_coarse=0,
        zone_fine=0,
        attenuation_cb=0,
        base_note=84,
        fine_tune=0,
        total_level=0,
        attack_rate=31,
        decay_rate=10,
        decay_level=0,
        release_rate=10,
        loop_enabled=True,
        loop_start=10,
        loop_end=100,
        pcm_sha256="a" * 64,
    )


def _model(label: str, row: SaturnToneSemanticRow) -> SaturnTonePolicyModel:
    return SaturnTonePolicyModel(
        label=label,
        melodic_sha256="b" * 64,
        drum_sha256="c" * 64,
        melodic_bytes=100,
        drum_bytes=50,
        sample_rate=11025,
        pcm8=False,
        rows=(row,),
    )


def test_changed_rows_reports_semantic_fields_not_only_hashes():
    before = _row()
    after = replace(before, attenuation_cb=120, total_level=32, sample_name="different")

    changes = _changed_rows(_model("old", before), _model("new", after))

    assert len(changes) == 1
    assert changes[0][0] is before
    assert changes[0][1] is after
    assert changes[0][2] == ("sample_name", "attenuation_cb", "total_level")


def test_in_memory_velocity_normalization_uses_sega_boottone_curve():
    payload = bytearray(64)
    struct.pack_into(">H", payload, 2, 16)
    payload[16:26] = b"0123456789"

    result = normalize_sega_velocity_curve_bytes(bytes(payload))

    assert result[16:26] == SEGA_BOOTTONE_VELOCITY_CURVE_0
    assert result[:16] == bytes(payload[:16])
    assert result[26:] == bytes(payload[26:])


def test_gate3e_reference_hashes_are_locked():
    assert GATE3E_MELODIC_SHA256 == "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
    assert GATE3E_DRUM_SHA256 == "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"


def test_revision_audit_cli_has_no_media_or_build_arguments():
    parser = build_parser()
    args = parser.parse_args(["--project", "GATE3E", "--soundfont", "GeneralUser.sf2"])

    assert args.project == Path("GATE3E")
    assert args.soundfont == Path("GeneralUser.sf2")
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--card-root" not in option_strings
    assert "--apply" not in option_strings
    assert "--output" not in option_strings
