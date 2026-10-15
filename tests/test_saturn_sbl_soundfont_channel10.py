from __future__ import annotations

import struct

import pytest

from rikai_kotoba.hardware.saturn import sbl_soundfont_gm as _gm
from rikai_kotoba.hardware.saturn.sbl_soundfont_channel10 import (
    SEGA_BOOTTONE_VELOCITY_CURVE_0,
    _channel10_selector,
    _resolve_global_local_zone,
    _space_spectre_merge_zone_maps,
    normalize_sega_velocity_curve,
    select_channel10_drum_preset,
)
from rikai_kotoba.hardware.saturn.sbl_soundfont_gm import (
    Sf2Data,
    Sf2Preset,
    SaturnSblSoundfontError,
)


def _preset(bank: int, name: str) -> Sf2Preset:
    # The selector only needs a non-empty zone tuple; zone contents are tested
    # by the compact converter's existing fixture suite.
    return Sf2Preset(name=name, program=0, bank=bank, zones=(object(),))  # type: ignore[arg-type]


def _packed_range(lo: int, hi: int) -> int:
    return lo | (hi << 8)


def test_channel10_prefers_bank_128_over_generaluser_bank_120_duplicate():
    sf2 = Sf2Data(
        smpl=b"",
        samples=(),
        presets=(
            _preset(120, "Standard 1 Kit"),
            _preset(128, "Standard 1"),
        ),
    )

    selected = select_channel10_drum_preset(
        sf2,
        fallback=lambda _sf2: pytest.fail("bank-128 channel-10 preset must win"),
    )

    assert selected.bank == 128
    assert selected.program == 0
    assert selected.name == "Standard 1"


def test_channel10_falls_back_when_soundfont_has_no_bank_128_percussion():
    bank120 = _preset(120, "Standard 1 Kit")
    sf2 = Sf2Data(smpl=b"", samples=(), presets=(bank120,))
    calls = []

    def fallback(value: Sf2Data) -> Sf2Preset:
        calls.append(value)
        return bank120

    selected = select_channel10_drum_preset(sf2, fallback=fallback)

    assert selected is bank120
    assert calls == [sf2]


def test_channel10_refuses_multiple_bank_128_standard_1_presets():
    sf2 = Sf2Data(
        smpl=b"",
        samples=(),
        presets=(
            _preset(128, "Standard 1"),
            _preset(128, "Standard 1 Kit"),
        ),
    )

    with pytest.raises(SaturnSblSoundfontError, match="not unique"):
        select_channel10_drum_preset(
            sf2,
            fallback=lambda _sf2: pytest.fail("ambiguous bank 128 must not fall back"),
        )


def test_local_zone_supersedes_same_level_global_generators():
    global_map = {
        _gm._GEN_ATTENUATION: 100,
        _gm._GEN_FINE_TUNE: 12,
        _gm._GEN_ATTACK: 80,
        _gm._GEN_KEY_RANGE: _packed_range(20, 100),
        _gm._GEN_VEL_RANGE: _packed_range(10, 120),
    }
    local_map = {
        _gm._GEN_ATTENUATION: 40,
        _gm._GEN_FINE_TUNE: -2,
        _gm._GEN_ATTACK: 20,
        _gm._GEN_KEY_RANGE: _packed_range(30, 90),
        _gm._GEN_VEL_RANGE: _packed_range(40, 100),
    }

    resolved = _resolve_global_local_zone(global_map, local_map)

    assert resolved[_gm._GEN_ATTENUATION] == 40
    assert resolved[_gm._GEN_FINE_TUNE] == -2
    assert resolved[_gm._GEN_ATTACK] == 20
    assert resolved[_gm._GEN_KEY_RANGE] == _packed_range(30, 90)
    assert resolved[_gm._GEN_VEL_RANGE] == _packed_range(40, 100)


def test_four_level_merge_resolves_locals_before_cross_level_addition():
    preset_global = {
        _gm._GEN_ATTENUATION: 100,
        _gm._GEN_FINE_TUNE: 12,
        _gm._GEN_ATTACK: 80,
        _gm._GEN_KEY_RANGE: _packed_range(20, 100),
        _gm._GEN_VEL_RANGE: _packed_range(10, 120),
    }
    preset_local = {
        _gm._GEN_ATTENUATION: 40,
        _gm._GEN_FINE_TUNE: -2,
        _gm._GEN_ATTACK: 20,
        _gm._GEN_KEY_RANGE: _packed_range(30, 90),
        _gm._GEN_VEL_RANGE: _packed_range(40, 100),
    }
    instrument_global = {
        _gm._GEN_ATTENUATION: 80,
        _gm._GEN_FINE_TUNE: 7,
        _gm._GEN_ATTACK: 70,
        _gm._GEN_KEY_RANGE: _packed_range(10, 80),
        _gm._GEN_VEL_RANGE: _packed_range(20, 127),
    }
    instrument_local = {
        _gm._GEN_ATTENUATION: 10,
        _gm._GEN_FINE_TUNE: 3,
        _gm._GEN_ATTACK: 30,
        _gm._GEN_KEY_RANGE: _packed_range(40, 70),
        _gm._GEN_VEL_RANGE: _packed_range(50, 90),
    }

    merged = _space_spectre_merge_zone_maps(
        preset_global,
        preset_local,
        instrument_global,
        instrument_local,
    )

    # Old all-four additive behavior produced attenuation 230. Correct SF2
    # hierarchy is preset local 40 + instrument local 10 = 50.
    assert merged[_gm._GEN_ATTENUATION] == 50
    assert merged[_gm._GEN_FINE_TUNE] == 1
    assert merged[_gm._GEN_ATTACK] == 50
    assert merged[_gm._GEN_KEY_RANGE] == _packed_range(40, 70)
    assert merged[_gm._GEN_VEL_RANGE] == _packed_range(50, 90)


def test_scoped_policy_restores_parser_hooks_after_exception():
    original_selector = _gm._select_drum_preset
    original_merge = _gm._merge_zone_maps

    with pytest.raises(RuntimeError, match="sentinel"):
        with _channel10_selector():
            assert _gm._select_drum_preset is not original_selector
            assert _gm._merge_zone_maps is _space_spectre_merge_zone_maps
            raise RuntimeError("sentinel")

    assert _gm._select_drum_preset is original_selector
    assert _gm._merge_zone_maps is original_merge


def test_velocity_table_is_normalized_to_sega_boottone_curve(tmp_path):
    tone = bytearray(40)
    struct.pack_into(">H", tone, 2, 16)
    tone[16:26] = b"0123456789"
    path = tmp_path / "tone.bin"
    path.write_bytes(tone)

    normalize_sega_velocity_curve(path)

    result = path.read_bytes()
    assert result[16:26] == SEGA_BOOTTONE_VELOCITY_CURVE_0
    assert result[:16] == bytes(tone[:16])
    assert result[26:] == bytes(tone[26:])


def test_velocity_table_rejects_out_of_range_offset(tmp_path):
    tone = bytearray(12)
    struct.pack_into(">H", tone, 2, 8)
    path = tmp_path / "tone.bin"
    path.write_bytes(tone)

    with pytest.raises(SaturnSblSoundfontError, match="offset is invalid"):
        normalize_sega_velocity_curve(path)
