from rikai_kotoba.hardware.saturn.sbl_velocity_curve import (
    SPACE_SPECTRE_SEGA_VELOCITY_TABLES,
    sega_velocity_level,
)
from rikai_kotoba.hardware.saturn.sbl_velocity_curve_fit import fit_velocity_table


def test_generic_fitter_preserves_physically_proven_space_spectre_tables():
    for amount, expected in SPACE_SPECTRE_SEGA_VELOCITY_TABLES.items():
        assert fit_velocity_table(amount) == expected


def test_generic_fitter_handles_generaluser_default_amount():
    table = fit_velocity_table(960)
    assert len(table) == 10
    assert sega_velocity_level(table, 127) == 127
    assert sega_velocity_level(table, 100) > sega_velocity_level(table, 64)
    assert sega_velocity_level(table, 64) > sega_velocity_level(table, 32)


def test_generic_fitter_is_deterministic_for_non_space_spectre_amount():
    first = fit_velocity_table(900)
    second = fit_velocity_table(900)
    assert first == second
    assert len(first) == 10
    assert sega_velocity_level(first, 127) == 127
