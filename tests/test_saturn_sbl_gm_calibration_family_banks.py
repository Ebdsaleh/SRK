from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_gm_calibration_family_banks.py"
)


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_calibration_families_cover_all_128_programs_without_placeholders():
    text = _source()
    assert "GM_FAMILY_COUNT = GM_PROGRAM_COUNT // GM_FAMILY_SIZE" in text
    assert "for family in range(GM_FAMILY_COUNT)" in text
    assert "for local_voice, program in enumerate(programs)" in text
    assert "covered != tuple(range(GM_PROGRAM_COUNT))" in text
    assert "silent placeholder PCM entered calibration family" in text
    assert "GM_FAMILY_FILENAME_TEMPLATE = \"GMC{family:02d}.BIN\"" in text


def test_calibration_families_apply_gate3f_fidelity_policy_to_any_gm_amount():
    text = _source()
    assert "from .sbl_fidelity_tone_authoring import _static_total_level" in text
    assert "from .sbl_velocity_curve_fit import fit_velocity_table" in text
    assert "fit_velocity_table(amount)" in text
    assert "total_level=_static_total_level(zone.attenuation_cb)" in text
    assert "data[0x1D] = velocity_table" in text
    assert "GM_CALIBRATION_TARGET_RATE = 11_025" in text
    assert "GM_CALIBRATION_PCM8 = False" in text


def test_calibration_families_use_existing_128_program_inventory():
    text = _source()
    assert "audit_gm_calibration_inventory(soundfont)" in text
    assert "GM_CALIBRATION_NOTE" in text
    assert "GM_CALIBRATION_VELOCITY" in text
    assert "rows_with_other_attenuation_modulators" in text
    assert "_select_melodic_preset(sf2, program)" in text
    assert "_choose_zone(" in text
