from pathlib import Path

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
    assert "_scope._resolve_row" in text


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
