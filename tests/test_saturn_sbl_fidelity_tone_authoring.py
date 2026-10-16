from __future__ import annotations

import pytest

from rikai_kotoba.hardware.saturn import sbl_soundfont_gm as gm
from rikai_kotoba.hardware.saturn.sbl_fidelity_tone_authoring import (
    SaturnFidelityToneAuthoringError,
    _pack_tone_bank,
    _static_total_level,
    _validate_velocity_table_catalog,
)
from rikai_kotoba.hardware.saturn.sbl_fidelity_tone_build_audit import _parse_bank
from rikai_kotoba.hardware.saturn.sbl_level_model_audit import (
    nearest_scsp_total_level,
    soundfont_static_attenuation_db,
)
from rikai_kotoba.hardware.saturn.sbl_velocity_curve import table_for_velocity_amount
from rikai_kotoba.tools.saturn_sbl_fidelity_tone_build_audit import _parser


def _one_voice_bank(tables: tuple[bytes, ...]) -> bytes:
    key = (7, 0, 4, 11025, 0)
    layer = gm.SaturnToneLayer(
        start_note=60,
        end_note=60,
        base_note=84,
        fine_tune=0,
        pcm_key=key,
        loop_start=0,
        loop_end=4,
        loop_enabled=False,
        pcm8=False,
        attack_rate=31,
        decay_rate=0,
        decay_level=0,
        release_rate=31,
        total_level=17,
    )
    voice = gm.SaturnToneVoice((layer,))
    block = gm._PcmBlock(key=key, data=b"\x00\x01\x00\x02\x00\x03\x00\x04")
    return _pack_tone_bank((voice,), (block,), pcm8=False, velocity_tables=tables)


def test_multi_velocity_tables_expand_ton_region_without_corrupting_voice() -> None:
    tables = (table_for_velocity_amount(500), table_for_velocity_amount(800))
    payload = _one_voice_bank(tables)
    parsed = _parse_bank(payload, kind="drum", required_keys={("drum", 0, 60)})

    assert parsed.velocity_tables == tables
    assert parsed.peg_offset - parsed.velocity_offset == 20
    assert parsed.voice_count == 1
    assert len(parsed.rows) == 1
    assert parsed.rows[0].base_note == 84
    assert parsed.rows[0].total_level == 17
    assert parsed.rows[0].velocity_table == 0


def test_static_total_level_uses_40_percent_soundfont_compatibility() -> None:
    target_db = soundfont_static_attenuation_db(815)
    expected, _ = nearest_scsp_total_level(target_db)
    assert target_db == pytest.approx(32.6)
    assert _static_total_level(815) == expected


def test_velocity_catalog_requires_ten_byte_tables() -> None:
    with pytest.raises(SaturnFidelityToneAuthoringError):
        _validate_velocity_table_catalog((b"short",))


def test_velocity_catalog_requires_at_least_one_table() -> None:
    with pytest.raises(SaturnFidelityToneAuthoringError):
        _validate_velocity_table_catalog(())


def test_corrected_ton_cli_is_read_only() -> None:
    parser = _parser()
    destinations = {action.dest for action in parser._actions}
    assert "project" in destinations
    assert "soundfont" in destinations
    assert "card_root" not in destinations
    assert "apply" not in destinations
    assert "confirm" not in destinations
    assert "output" not in destinations


def test_historical_base_packer_still_emits_one_velocity_table() -> None:
    key = (9, 0, 2, 11025, 0)
    layer = gm.SaturnToneLayer(
        start_note=64,
        end_note=64,
        base_note=88,
        fine_tune=0,
        pcm_key=key,
        loop_start=0,
        loop_end=2,
        loop_enabled=False,
        pcm8=False,
        attack_rate=31,
        decay_rate=0,
        decay_level=0,
        release_rate=31,
        total_level=0,
    )
    voice = gm.SaturnToneVoice((layer,))
    block = gm._PcmBlock(key=key, data=b"\x00\x00\x00\x00")
    payload = gm._build_tone_bank((voice,), (block,), pcm8=False)
    velocity = int.from_bytes(payload[2:4], "big")
    peg = int.from_bytes(payload[4:6], "big")
    assert peg - velocity == 10
