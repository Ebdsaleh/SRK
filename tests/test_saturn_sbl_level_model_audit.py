from __future__ import annotations

import struct

import pytest

from rikai_kotoba.hardware.saturn.sbl_level_model_audit import (
    SF2_INITIAL_ATTENUATION_DESTINATION,
    nearest_scsp_total_level,
    parse_sf2_modulators,
    soundfont_static_attenuation_db,
)
from rikai_kotoba.tools.saturn_sbl_level_model_audit import build_parser


def test_soundfont_static_attenuation_uses_compatibility_40_percent_rule():
    assert soundfont_static_attenuation_db(0) == pytest.approx(0.0)
    assert soundfont_static_attenuation_db(250) == pytest.approx(10.0)
    assert soundfont_static_attenuation_db(815) == pytest.approx(32.6)
    assert soundfont_static_attenuation_db(-100) == pytest.approx(0.0)


def test_nearest_scsp_total_level_quantizes_documented_attenuation():
    level, attenuation = nearest_scsp_total_level(32.6)
    assert 0 <= level <= 255
    assert attenuation == pytest.approx(32.6, abs=0.2)


def test_parse_sf2_modulators_finds_explicit_initial_attenuation_destination():
    active = struct.pack(
        "<HHhHH",
        0x0002,
        SF2_INITIAL_ATTENUATION_DESTINATION,
        120,
        0x0000,
        0x0000,
    )
    terminal = bytes(10)

    records = parse_sf2_modulators(active + terminal, table="imod")

    assert len(records) == 1
    record = records[0]
    assert record.table == "imod"
    assert record.index == 0
    assert record.source == 0x0002
    assert record.destination == SF2_INITIAL_ATTENUATION_DESTINATION
    assert record.amount == 120


def test_parse_sf2_modulators_rejects_misaligned_chunk():
    with pytest.raises(Exception, match="10-byte"):
        parse_sf2_modulators(b"bad", table="pmod")


def test_level_model_cli_is_read_only_and_has_no_media_or_output_arguments():
    parser = build_parser()
    args = parser.parse_args(["--project", "GATE3E"])
    assert str(args.project) == "GATE3E"
    assert args.soundfont is None
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--card-root" not in option_strings
    assert "--apply" not in option_strings
    assert "--output" not in option_strings
    assert "--confirm" not in option_strings
