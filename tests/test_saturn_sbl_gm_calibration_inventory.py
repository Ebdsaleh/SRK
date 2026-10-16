from pathlib import Path

from rikai_kotoba.hardware.saturn import sbl_soundfont_gm as _gm
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_inventory import (
    _zone_matches_selected,
)
from rikai_kotoba.tools.saturn_sbl_gm_calibration_inventory import build_parser


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "rikai_kotoba" / "hardware" / "saturn" / "sbl_gm_calibration_inventory.py"


def test_inventory_contract_is_all_128_programs_at_fixed_c4_velocity_100():
    text = SOURCE.read_text(encoding="utf-8")
    assert "GM_PROGRAM_COUNT = 128" in text
    assert "GM_FAMILY_SIZE = 8" in text
    assert "GM_CALIBRATION_NOTE = 60" in text
    assert "GM_CALIBRATION_VELOCITY = 100" in text
    assert "for program in range(GM_PROGRAM_COUNT)" in text
    assert "selected = _gm._choose_zone(" in text
    assert "_resolve_calibration_row(semantic, selected, **raw)" in text


def test_inventory_reconstructs_the_full_selected_zone_before_reading_modulators():
    selected = _gm.Sf2PresetZone(
        key_lo=48,
        key_hi=72,
        vel_lo=64,
        vel_hi=127,
        sample_id=42,
        start_offset=7,
        end_offset=-3,
        loop_start_offset=5,
        loop_end_offset=-2,
        attenuation_cb=321,
        coarse_tune=1,
        fine_tune=-9,
        attack_tc=-1000,
        decay_tc=-900,
        sustain_cb=200,
        release_tc=-800,
        sample_modes=1,
        root_key=60,
        scale_tuning=100,
    )
    mapping = {
        _gm._GEN_KEY_RANGE: 48 | (72 << 8),
        _gm._GEN_VEL_RANGE: 64 | (127 << 8),
        _gm._GEN_SAMPLE_ID: 42,
        _gm._GEN_START: 7,
        _gm._GEN_END: -3,
        _gm._GEN_LOOP_START: 5,
        _gm._GEN_LOOP_END: -2,
        _gm._GEN_ATTENUATION: 321,
        _gm._GEN_COARSE_TUNE: 1,
        _gm._GEN_FINE_TUNE: -9,
        _gm._GEN_ATTACK: -1000,
        _gm._GEN_DECAY: -900,
        _gm._GEN_SUSTAIN: 200,
        _gm._GEN_RELEASE: -800,
        _gm._GEN_SAMPLE_MODES: 1,
        _gm._GEN_ROOT_KEY: 60,
        _gm._GEN_SCALE_TUNING: 100,
    }

    assert _zone_matches_selected(mapping, selected)

    changed = dict(mapping)
    changed[_gm._GEN_ATTACK] = -999
    assert not _zone_matches_selected(changed, selected)


def test_inventory_uses_raw_order_only_after_full_zone_identity_matches():
    text = SOURCE.read_text(encoding="utf-8")
    assert "if not _zone_matches_selected(merged, selected):" in text
    assert "key=lambda candidate: (candidate[0], candidate[1])" in text
    assert "parse_soundfont_bytes" in text
    assert "_choose_zone`` is stable" in text
    assert "_scope._resolve_row(semantic, **raw)" not in text


def test_inventory_refuses_to_hide_non_velocity_attenuation_modulators():
    text = SOURCE.read_text(encoding="utf-8")
    assert "rows_with_other_attenuation_modulators" in text
    assert "mod.identity != _scope.default_velocity_identity()" in text


def test_inventory_cli_is_read_only():
    parser = build_parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--soundfont" in option_strings
    for forbidden in (
        "--project", "--card-root", "--output", "--apply", "--confirm",
        "--destination", "--deploy",
    ):
        assert forbidden not in option_strings
